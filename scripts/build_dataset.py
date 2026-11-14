"""Build the processed data the API serves.

  - hotspots.parquet: every hotspot, clipped to The Gambia, with its region, district
    and harmonized weight
  - harmonization.json: the fitted conversion and its validation results
  - areas.json: area and label position of every region and district

Run after scripts/download_data.py:
    uv run python scripts/build_dataset.py
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd

from firecal import harmonize
from firecal.data import BOUNDARIES, PROCESSED, load_raw_hotspots

# Hotspot coordinates are pixel centres, and the boundary file is simplified, so a
# fire on the border can sit just outside the polygon. Keep points within about 1 km.
BORDER_TOLERANCE_M = 1000
UTM_28N = "EPSG:32628"


def districts_with_regions() -> gpd.GeoDataFrame:
    districts = gpd.read_file(BOUNDARIES / "gambia_adm2.geojson")[["shapeName", "geometry"]]
    districts = districts.rename(columns={"shapeName": "district"})
    regions = gpd.read_file(BOUNDARIES / "gambia_adm1.geojson")[["shapeName", "geometry"]]
    regions = regions.rename(columns={"shapeName": "region"})
    # geoBoundaries does not record which region a district belongs to, so place each
    # district by a point guaranteed to lie inside it.
    inside = gpd.GeoDataFrame(districts[["district"]], geometry=districts.representative_point(), crs=districts.crs)
    placed = gpd.sjoin_nearest(inside.to_crs(UTM_28N), regions.to_crs(UTM_28N), how="left")
    districts["region"] = placed["region"].to_numpy()
    return districts


def area_facts(districts: gpd.GeoDataFrame) -> dict:
    """Size and a label position for each region and district. `districts` is in UTM metres."""
    facts = {}
    for level, shapes in {"district": districts, "region": districts.dissolve("region").reset_index()}.items():
        label_points = shapes.representative_point().to_crs("EPSG:4326")
        facts[level] = {
            name: {"area_km2": round(area / 1e6, 1), "label": [round(point.y, 4), round(point.x, 4)]}
            for name, area, point in zip(shapes[level], shapes.area, label_points, strict=True)
        }
    return facts


def main() -> None:
    hotspots = load_raw_hotspots()
    districts = districts_with_regions().to_crs(UTM_28N)

    points = gpd.GeoDataFrame(
        hotspots,
        geometry=gpd.points_from_xy(hotspots["longitude"], hotspots["latitude"]),
        crs="EPSG:4326",
    ).to_crs(UTM_28N)
    joined = gpd.sjoin_nearest(points, districts, how="left", max_distance=BORDER_TOLERANCE_M, distance_col="dist_m")
    # A point exactly between two districts matches both; keep one.
    joined = joined[~joined.index.duplicated(keep="first")]

    inside = joined["district"].notna()
    dropped = (~inside).groupby(joined["source"]).sum()
    result = pd.DataFrame(joined[inside].drop(columns=["geometry", "index_right", "dist_m"]))
    result = result.sort_values(["acq_date", "sensor"]).reset_index(drop=True)

    model = harmonize.fit(result)
    model["confidence_check"] = harmonize.confidence_check(result)
    result = harmonize.apply(result, model)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "harmonization.json").write_text(json.dumps(model, indent=2))
    (PROCESSED / "areas.json").write_text(json.dumps(area_facts(districts), indent=2))
    out = PROCESSED / "hotspots.parquet"
    result.to_parquet(out, index=False)

    print(f"wrote {out.relative_to(PROCESSED.parents[1])}: {len(result):,} hotspots")
    print("outside the border, dropped:", {k: int(v) for k, v in dropped.items() if v})
    print(result.groupby(["sensor", "source"]).size().to_string())
    print("regions:", result.groupby("region").size().sort_values(ascending=False).to_dict())
    print("range:", result["acq_date"].min().date(), "to", result["acq_date"].max().date())
    modis, terra = model["eras"]["modis"], model["eras"]["terra"]
    print(f"MODIS to VIIRS: factor {modis['overall_factor']}, interval {modis['interval']}")
    for level, errors in modis["validation"].items():
        print(f"  held-out error, {level}: {errors}")
    for check in model["confidence_check"]:
        print(f"  confidence rule {check['rule']}: {check}")
    print(
        f"Terra to MODIS: factor {terra['terra_to_modis']}, interval {terra['interval']}, error {terra['validation']}"
    )
    print("harmonized season totals:", result.groupby("season")["h"].sum().round().astype(int).to_dict())


if __name__ == "__main__":
    main()
