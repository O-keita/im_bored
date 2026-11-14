"""HTTP API for the Gambia fire calendar.

Run with:
    uv run uvicorn firecal.api:app --reload --port 8010
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from firecal.data import BOUNDARIES, PROCESSED, load_hotspots
from firecal.query import Query, UnknownArea, calendar, select
from firecal.summary import calendar_table, summarise

# The map draws at most this many points; the CSV download always has every row.
MAX_MAP_POINTS = 8000
CSV_COLUMNS = [
    "acq_date", "acq_time", "latitude", "longitude", "sensor", "satellite", "daynight",
    "confidence", "frp", "source", "region", "district", "season", "h", "h_kind",
]  # fmt: skip

app = FastAPI(title="Gambia Fire Calendar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _select(query: Query):
    try:
        return select(load_hotspots(), query)
    except UnknownArea as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/health")
def health() -> dict:
    hotspots = load_hotspots()
    return {
        "status": "ok",
        "hotspots": len(hotspots),
        "first_date": hotspots["acq_date"].min().date().isoformat(),
        "last_date": hotspots["acq_date"].max().date().isoformat(),
    }


@lru_cache(maxsize=1)
def _area_facts() -> dict:
    return json.loads((PROCESSED / "areas.json").read_text())


@app.get("/api/areas")
def areas() -> dict:
    """Regions and their districts, with size, a label position and how much each burns.

    `per_100km2` is the median harmonized hotspots per complete season, per 100 square
    kilometres, so that large and small areas can be compared on the map.
    """
    hotspots = load_hotspots()
    facts = _area_facts()
    complete = hotspots[hotspots["season"] < hotspots["season"].max()]

    def describe(level: str, name: str) -> dict:
        by_season = complete[complete[level] == name].groupby("season")["h"].sum()
        median = float(
            by_season.reindex(range(complete["season"].min(), complete["season"].max() + 1)).fillna(0).median()
        )
        fact = facts[level][name]
        return {
            "name": name,
            "area_km2": fact["area_km2"],
            "label": fact["label"],
            "median_season": round(median, 1),
            "per_100km2": round(median / fact["area_km2"] * 100, 1),
        }

    pairs = hotspots[["region", "district"]].drop_duplicates().sort_values(["region", "district"])
    return {
        "regions": [
            {**describe("region", region), "districts": [describe("district", d) for d in rows["district"]]}
            for region, rows in pairs.groupby("region")
        ]
    }


@app.get("/api/method")
def method() -> dict:
    """The fitted harmonization and how well it predicted seasons it had not seen."""
    return json.loads((PROCESSED / "harmonization.json").read_text())


@lru_cache(maxsize=2)
def _boundary(level: str) -> dict:
    return json.loads((BOUNDARIES / f"gambia_{level}.geojson").read_text())


@app.get("/api/boundaries/{level}")
def boundaries(level: str) -> dict:
    """GeoJSON outlines. `adm1` is the 8 regions, `adm2` the 48 districts."""
    if level not in {"adm0", "adm1", "adm2"}:
        raise HTTPException(status_code=404, detail="level must be adm0, adm1 or adm2")
    return _boundary(level)


@app.post("/api/calendar")
def calendar_endpoint(query: Query) -> dict:
    """Raw counts per sensor, before harmonization. Kept so the two records can be compared."""
    return calendar(_select(query))


@app.post("/api/summary")
def summary_endpoint(query: Query) -> dict:
    """The harmonized calendar, season totals, the normal season and how this month compares."""
    hotspots = load_hotspots()
    area_only = Query(area=query.area)
    try:
        area_rows = select(hotspots, area_only)
    except UnknownArea as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return summarise(area_rows, hotspots["acq_date"].max(), query.start, query.end)


@app.post("/api/calendar.csv")
def calendar_csv(query: Query) -> Response:
    """The harmonized calendar of the selection, one row per month, as a CSV download."""
    hotspots = load_hotspots()
    try:
        area_rows = select(hotspots, Query(area=query.area))
    except UnknownArea as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    table = calendar_table(area_rows, hotspots["acq_date"].max(), query.start, query.end)
    return Response(
        content=table.to_csv(index=False),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="gambia_burning_calendar.csv"'},
    )


@app.post("/api/hotspots")
def hotspots_endpoint(query: Query) -> dict:
    """Points for the map, newest last. Large selections are thinned evenly through time."""
    selected = _select(query)
    detections = len(selected)
    # Draw only the detections that make up the harmonized series, so that a fire seen
    # by two sensors is one dot. The CSV still has every detection.
    selected = selected[selected["h"] > 0]
    total = len(selected)
    if total > MAX_MAP_POINTS:
        selected = selected.iloc[:: -(-total // MAX_MAP_POINTS)]
    points = selected[["latitude", "longitude", "acq_date", "frp"]]
    return {
        "detections": detections,
        "total": total,
        "shown": len(points),
        # Parallel arrays keep the payload small: [latitude, longitude, date, fire radiative power].
        "points": [
            [round(lat, 4), round(lon, 4), day.strftime("%Y-%m-%d"), frp]
            for lat, lon, day, frp in points.itertuples(index=False)
        ],
    }


@app.post("/api/hotspots.csv")
def hotspots_csv(query: Query) -> Response:
    """Every hotspot in the selection, as a CSV download."""
    selected = _select(query)[CSV_COLUMNS]
    body = selected.to_csv(index=False, date_format="%Y-%m-%d")
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="gambia_hotspots.csv"'},
    )
