"""Select hotspots by area and date range, and summarise them as a burning calendar."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator
from shapely import contains_xy
from shapely.geometry import Polygon

EARTH_RADIUS_KM = 6371.0088
# Fire season months in display order: July first, June last.
SEASON_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]


class Country(BaseModel):
    type: Literal["country"] = "country"


class Region(BaseModel):
    type: Literal["region"]
    name: str


class District(BaseModel):
    type: Literal["district"]
    name: str


class Circle(BaseModel):
    type: Literal["circle"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=500)


class PolygonArea(BaseModel):
    type: Literal["polygon"]
    # Ring of [longitude, latitude] pairs, GeoJSON order. Closing the ring is optional.
    coordinates: list[tuple[float, float]] = Field(min_length=3)


Area = Annotated[Country | Region | District | Circle | PolygonArea, Field(discriminator="type")]


class Query(BaseModel):
    area: Area = Country()
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _ordered(self) -> Query:
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must not be after end")
        return self


class UnknownArea(ValueError):
    pass


def _in_area(hotspots: pd.DataFrame, area: Area) -> np.ndarray:
    if isinstance(area, Country):
        return np.ones(len(hotspots), dtype=bool)
    if isinstance(area, Region | District):
        column = hotspots[area.type]
        if area.name not in set(column.unique()):
            raise UnknownArea(f"No {area.type} named {area.name!r}")
        return (column == area.name).to_numpy()
    lat = hotspots["latitude"].to_numpy()
    lon = hotspots["longitude"].to_numpy()
    if isinstance(area, Circle):
        lat0, lon0 = np.radians(area.latitude), np.radians(area.longitude)
        lat1, lon1 = np.radians(lat), np.radians(lon)
        h = np.sin((lat1 - lat0) / 2) ** 2 + np.cos(lat0) * np.cos(lat1) * np.sin((lon1 - lon0) / 2) ** 2
        return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h)) <= area.radius_km
    polygon = Polygon(area.coordinates)
    if not polygon.is_valid:
        raise UnknownArea("The polygon crosses itself. Draw it without overlapping edges.")
    return contains_xy(polygon, lon, lat)


def select(hotspots: pd.DataFrame, query: Query) -> pd.DataFrame:
    """Rows of `hotspots` inside the query's area and date range."""
    mask = _in_area(hotspots, query.area)
    if query.start:
        mask = mask & (hotspots["acq_date"] >= pd.Timestamp(query.start)).to_numpy()
    if query.end:
        mask = mask & (hotspots["acq_date"] <= pd.Timestamp(query.end)).to_numpy()
    return hotspots[mask]


def calendar(selected: pd.DataFrame) -> dict:
    """Hotspot counts per sensor, fire season and month.

    These are raw counts. The sensors are not comparable until they are harmonized,
    which is why each sensor gets its own grid.
    """
    sensors = {}
    for sensor, rows in selected.groupby("sensor"):
        counts = rows.groupby(["season", "month"]).size()
        seasons = sorted(rows["season"].unique().tolist())
        sensors[sensor] = {
            "seasons": seasons,
            "counts": [[int(counts.get((season, month), 0)) for month in SEASON_MONTHS] for season in seasons],
            "total": len(rows),
            "first_date": rows["acq_date"].min().date().isoformat(),
            "last_date": rows["acq_date"].max().date().isoformat(),
        }
    return {"months": SEASON_MONTHS, "harmonized": False, "sensors": sensors}
