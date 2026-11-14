import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from firecal.api import MAX_MAP_POINTS, app
from firecal.data import load_hotspots

client = TestClient(app)


def test_health_reports_the_whole_record():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["hotspots"] == len(load_hotspots())
    assert body["first_date"] == "2000-11-06"


def test_areas_lists_eight_regions_and_all_districts():
    regions = client.get("/api/areas").json()["regions"]
    assert len(regions) == 8
    assert sum(len(r["districts"]) for r in regions) == load_hotspots()["district"].nunique()


def test_calendar_counts_match_the_table():
    query = {"area": {"type": "region", "name": "Basse"}, "start": "2022-07-01", "end": "2023-06-30"}
    body = client.post("/api/calendar", json=query).json()
    table = load_hotspots()
    expected = table[(table["region"] == "Basse") & (table["season"] == 2023)].groupby("sensor").size()
    assert body["harmonized"] is False
    assert body["months"][0] == 7 and body["months"][-1] == 6
    for sensor, grid in body["sensors"].items():
        assert grid["seasons"] == [2023]
        assert sum(grid["counts"][0]) == grid["total"] == expected[sensor]


def test_circle_and_polygon_select_the_same_square_of_points():
    # A polygon far larger than a small circle must contain every point the circle does.
    circle = {"type": "circle", "latitude": 13.45, "longitude": -15.0, "radius_km": 10}
    square = {"type": "polygon", "coordinates": [[-15.3, 13.2], [-14.7, 13.2], [-14.7, 13.7], [-15.3, 13.7]]}
    in_circle = client.post("/api/hotspots", json={"area": circle}).json()["detections"]
    in_square = client.post("/api/hotspots", json={"area": square}).json()["detections"]
    assert 0 < in_circle < in_square < len(load_hotspots())


def test_map_points_are_capped_but_csv_is_complete():
    query = {"area": {"type": "country"}, "start": "2023-01-01", "end": "2023-12-31"}
    points = client.post("/api/hotspots", json=query).json()
    assert points["shown"] == len(points["points"]) <= MAX_MAP_POINTS
    assert points["total"] < points["detections"]  # three sensors saw 2023, one is drawn
    csv = pd.read_csv(io.StringIO(client.post("/api/hotspots.csv", json=query).text))
    assert len(csv) == points["detections"]
    assert csv["acq_date"].min() >= "2023-01-01" and csv["acq_date"].max() <= "2023-12-31"


def test_harmonized_weights_count_each_fire_once():
    table = load_hotspots()
    # While S-NPP flew it is the only sensor counted, at one hotspot per detection.
    in_2020 = table[table["season"] == 2020]
    assert in_2020["h"].sum() == (in_2020["sensor"] == "VIIRS_SNPP").sum()
    # Before VIIRS, every MODIS detection is scaled up and nothing else exists.
    in_2008 = table[table["season"] == 2008]
    assert set(in_2008["sensor"]) == {"MODIS"}
    assert (
        (in_2008["h"] > 1).all() and (in_2008["h_lo"] < in_2008["h"]).all() and (in_2008["h_hi"] > in_2008["h"]).all()
    )
    assert 4 < in_2008["h"].mean() < 7
    # After S-NPP stopped, NOAA-20 carries the series.
    latest = table[table["acq_date"] > "2026-11-01"]
    assert set(latest.loc[latest["h"] > 0, "sensor"]) == {"VIIRS_NOAA20"}


def test_summary_is_consistent_with_the_table():
    body = client.post("/api/summary", json={"area": {"type": "region", "name": "Basse"}}).json()
    table = load_hotspots()
    basse = table[table["region"] == "Basse"]
    assert body["current_season"] == 2027 and body["as_of"] == "2026-11-14"
    assert body["calendar"]["seasons"] == list(range(2001, 2028))
    by_season = {s["season"]: s for s in body["seasons"]}
    assert by_season[2020]["total"] == pytest.approx(basse.loc[basse["season"] == 2020, "h"].sum(), abs=0.1)
    assert sum(body["calendar"]["counts"][19]) == pytest.approx(by_season[2020]["total"], abs=1)
    assert by_season[2005]["kind"] == "converted" and by_season[2012]["kind"] == "mixed"
    assert by_season[2020]["kind"] == "observed" and by_season[2020]["low"] == by_season[2020]["high"]
    assert by_season[2005]["low"] < by_season[2005]["total"] < by_season[2005]["high"]
    assert by_season[2027]["complete"] is False
    assert body["typical"]["peak_month"] in {1, 2, 3, 4, 5}
    assert body["typical"]["seasons_used"] == 26


def test_date_range_narrows_the_calendar_but_not_what_is_normal():
    area = {"type": "region", "name": "Kuntaur"}
    full = client.post("/api/summary", json={"area": area}).json()
    narrow = client.post("/api/summary", json={"area": area, "start": "2015-01-01", "end": "2018-03-01"}).json()
    assert narrow["calendar"]["seasons"] == [2015, 2016, 2017, 2018]
    assert narrow["normal"] == full["normal"] and narrow["current"] == full["current"]


def test_areas_and_method_describe_the_record():
    regions = {r["name"]: r for r in client.get("/api/areas").json()["regions"]}
    assert regions["Basse"]["area_km2"] > 1000 and regions["Basse"]["per_100km2"] > regions["Banjul"]["per_100km2"]
    assert len(regions["Basse"]["label"]) == 2
    method = client.get("/api/method").json()
    assert method["viirs_start"] == "2012-01-20" and method["snpp_end"] == "2026-11-01"
    modis = method["eras"]["modis"]
    assert len(modis["held_out_seasons"]) == 14
    # The regression is the conversion in use, so it has to beat both baselines on held-out seasons.
    for errors in modis["validation"].values():
        assert errors["count_model"] < min(errors["single_factor"], errors["month_and_region"])
    assert modis["validation"]["national_season"]["count_model"] < 0.07
    assert 0.5 < modis["count_model"]["exponent"] < 1


def test_busier_months_convert_at_a_lower_rate():
    table = load_hotspots()
    converted = table[(table["h_kind"] == "converted") & (table["region"] == "Basse") & (table["month"] == 2)]
    by_season = converted.groupby("season")["h"].agg(["size", "mean"]).sort_values("size")
    assert by_season["mean"].iloc[0] > by_season["mean"].iloc[-1]
    # Within one region and month every detection carries the same weight, so any drawn area adds up.
    one_month = converted[converted["season"] == 2008]
    assert one_month["h"].nunique() == 1


def test_every_detection_is_kept_because_dropping_low_confidence_predicts_no_better():
    checks = {c["rule"]: c for c in client.get("/api/method").json()["confidence_check"]}
    assert set(checks) == {"keep_all", "drop_modis_low", "drop_viirs_low", "drop_both"}
    assert checks["keep_all"]["dropped_share"] == 0
    for rule in ("drop_modis_low", "drop_viirs_low", "drop_both"):
        assert checks[rule]["region_season"] >= checks["keep_all"]["region_season"]
        assert checks[rule]["national_season"] >= checks["keep_all"]["national_season"]


@pytest.mark.parametrize(
    ("query", "status"),
    [
        ({"area": {"type": "region", "name": "Atlantis"}}, 404),
        ({"area": {"type": "country"}, "start": "2024-01-01", "end": "2023-01-01"}, 422),
        ({"area": {"type": "circle", "latitude": 13.4, "longitude": -15.0, "radius_km": 0}}, 422),
        ({"area": {"type": "polygon", "coordinates": [[-15, 13], [-14, 14], [-14, 13], [-15, 14]]}}, 404),
    ],
)
def test_bad_queries_are_rejected(query, status):
    assert client.post("/api/calendar", json=query).status_code == status


def test_calendar_csv_matches_the_summary_and_the_raw_counts():
    query = {"area": {"type": "region", "name": "Basse"}, "start": "2009-07-01", "end": "2014-06-30"}
    csv = pd.read_csv(io.StringIO(client.post("/api/calendar.csv", json=query).text))
    summary = client.post("/api/summary", json=query).json()
    assert len(csv) == 5 * 12 and set(csv["season"]) == {"2009/10", "2010/11", "2011/12", "2012/13", "2013/14"}
    assert csv["hotspots"].sum() == pytest.approx(sum(s["total"] for s in summary["seasons"]), abs=1)
    table = load_hotspots()
    basse = table[(table["region"] == "Basse") & table["season"].between(2010, 2014)]
    assert csv["modis_detections"].sum() == (basse["sensor"] == "MODIS").sum()
    assert csv["viirs_snpp_detections"].sum() == (basse["sensor"] == "VIIRS_SNPP").sum()
    february_2010 = csv[(csv["year"] == 2010) & (csv["month"] == 2)].iloc[0]
    assert february_2010["basis"] == "converted"
    assert february_2010["likely_low"] < february_2010["hotspots"] < february_2010["likely_high"]
    february_2014 = csv[(csv["year"] == 2014) & (csv["month"] == 2)].iloc[0]
    assert february_2014["basis"] == "observed" and february_2014["hotspots"] == february_2014["viirs_snpp_detections"]
    assert (csv["difference_from_median"] == (csv["hotspots"] - csv["median_for_month"]).round(1)).all()


def test_calendar_csv_stops_at_the_current_month():
    csv = pd.read_csv(io.StringIO(client.post("/api/calendar.csv", json={"area": {"type": "country"}}).text))
    last = csv.iloc[-1]
    assert (last["year"], last["month"]) == (2026, 11) and not last["month_complete"]
    assert csv["month_complete"].sum() == len(csv) - 1


def test_last_week_is_compared_with_the_same_week_and_the_record_week():
    body = client.post("/api/summary", json={"area": {"type": "country"}}).json()
    week = body["last_week"]
    table = load_hotspots()
    recent = table[(table["acq_date"] >= "2026-11-08") & (table["acq_date"] <= "2026-11-14")]
    assert (week["from"], week["to"]) == ("2026-11-08", "2026-11-14")
    assert week["total"] == pytest.approx(recent["h"].sum(), abs=0.1)
    # The busiest week on record falls in the burning season and dwarfs a week in mid November.
    assert week["record_total"] > 10 * max(week["total"], 1)
    assert week["record_to"][5:7] in {"01", "02", "03", "04", "05"}
    daily = table.groupby("acq_date")["h"].sum()
    in_record = daily[(daily.index >= week["record_from"]) & (daily.index <= week["record_to"])]
    assert in_record.sum() == pytest.approx(week["record_total"], abs=0.1)
