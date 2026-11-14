"""Turn the harmonized hotspots of one area into a burning calendar and plain findings."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from firecal.data import fire_season

# Fire season months in display order: July first, June last.
SEASON_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip
# A season with fewer harmonized hotspots than this is too thin to time its start and end.
MIN_FOR_TIMING = 20
WEEK = 7


def _status(percentile: float) -> str:
    if percentile >= 90:
        return "well above normal"
    if percentile >= 75:
        return "above normal"
    if percentile > 25:
        return "near normal"
    if percentile > 10:
        return "below normal"
    return "well below normal"


def _percentile(history: np.ndarray, value: float) -> float:
    """Share of past values at or below `value`, in percent."""
    return float((history <= value).mean() * 100) if len(history) else 50.0


def _season_day(dates: pd.Series) -> pd.Series:
    """Days since 1 July of the season the date belongs to."""
    start = pd.to_datetime({"year": fire_season(dates) - 1, "month": 7, "day": 1})
    return (dates - start).dt.days


def _day_label(season_day: float) -> str:
    """A season day as a rough calendar position, such as 'mid November'."""
    day = pd.Timestamp(2001, 7, 1) + pd.Timedelta(days=round(season_day))
    part = "early" if day.day <= 10 else "mid" if day.day <= 20 else "late"
    return f"{part} {MONTH_NAMES[day.month - 1]}"


def summarise(area_rows: pd.DataFrame, today: pd.Timestamp, start: date | None, end: date | None) -> dict:
    """Calendar, season totals, normal season shape and how the current month compares.

    `area_rows` is every hotspot in the selected area, whatever its date. The date range
    only narrows which seasons the calendar and totals show. What counts as normal always
    comes from the whole record, so narrowing the dates does not change it.
    """
    rows = area_rows[area_rows["h"] > 0]
    current_season = int(today.year + (today.month >= 7))
    first_season = int(rows["season"].min()) if len(rows) else current_season
    all_seasons = list(range(first_season, current_season + 1))
    complete = [s for s in all_seasons if s < current_season]

    monthly = rows.groupby(["season", "month"])["h"].sum()
    grid = pd.DataFrame(
        [[float(monthly.get((s, m), 0.0)) for m in SEASON_MONTHS] for s in all_seasons],
        index=all_seasons,
        columns=SEASON_MONTHS,
    )
    totals = rows.groupby("season")[["h", "h_lo", "h_hi"]].sum().reindex(all_seasons).fillna(0.0)
    converted_share = (
        rows[rows["h_kind"] == "converted"].groupby("season")["h"].sum().reindex(all_seasons).fillna(0.0)
        / totals["h"].replace(0, np.nan)
    ).fillna(0.0)

    def kind(season: int) -> str:
        share = converted_share[season]
        return "converted" if share > 0.99 else "observed" if share < 0.01 else "mixed"

    shown = [
        s
        for s in all_seasons
        if (start is None or pd.Timestamp(start) <= pd.Timestamp(s, 6, 30))
        and (end is None or pd.Timestamp(end) >= pd.Timestamp(s - 1, 7, 1))
    ]

    history = grid.loc[complete]
    normal = {
        "median": [round(float(v), 1) for v in history.median()],
        "low": [round(float(v), 1) for v in history.quantile(0.25)],
        "high": [round(float(v), 1) for v in history.quantile(0.75)],
    }
    season_history = totals.loc[complete, "h"]
    ranked = season_history.sort_values(ascending=False)

    # The month in progress is compared with the same days of that month in earlier seasons.
    in_month = rows[(rows["month"] == today.month) & (rows["acq_date"].dt.day <= today.day)]
    month_to_date = in_month.groupby("season")["h"].sum().reindex(all_seasons).fillna(0.0)
    month_history = month_to_date.loc[complete].to_numpy()
    month_now = float(month_to_date[current_season])
    month_median = float(np.median(month_history)) if len(month_history) else 0.0
    month_percentile = _percentile(month_history, month_now)

    season_day_now = (today - pd.Timestamp(current_season - 1, 7, 1)).days
    to_date = rows[_season_day(rows["acq_date"]) <= season_day_now].groupby("season")["h"].sum()
    to_date = to_date.reindex(all_seasons).fillna(0.0)
    season_now = float(to_date[current_season])
    season_to_date_history = to_date.loc[complete].to_numpy()

    # When burning usually starts and ends: the day a season passes 10% and 90% of its own total.
    timing = rows[rows["season"].isin(complete)].assign(day=lambda r: _season_day(r["acq_date"]))
    starts, ends = [], []
    for _, season_rows in timing.groupby("season"):
        if season_rows["h"].sum() < MIN_FOR_TIMING:
            continue
        ordered = season_rows.sort_values("day")
        share = ordered["h"].cumsum() / ordered["h"].sum()
        starts.append(ordered["day"].to_numpy()[np.searchsorted(share.to_numpy(), 0.1)])
        ends.append(ordered["day"].to_numpy()[np.searchsorted(share.to_numpy(), 0.9)])

    # The last seven days against the same seven days of every earlier season, and against
    # the busiest seven days this area has had. This is how a fire burning now is compared
    # with previous ones: by how much the satellites saw in and around it.
    days = _season_day(rows["acq_date"])
    in_week = rows[(days > season_day_now - WEEK) & (days <= season_day_now)]
    week = in_week.groupby("season")["h"].sum().reindex(all_seasons).fillna(0.0)
    week_now = float(week[current_season])
    week_history = week.loc[complete].to_numpy()
    daily = rows.groupby("acq_date")["h"].sum()
    if len(daily):
        daily = daily.reindex(pd.date_range(daily.index.min(), today, freq="D"), fill_value=0.0)
        rolling = daily.rolling(WEEK, min_periods=1).sum()
        record_end, record_total = rolling.idxmax(), float(rolling.max())
    else:
        record_end, record_total = None, 0.0

    peak_index = int(np.argmax(normal["median"])) if len(complete) else 0
    return {
        "unit": "VIIRS-equivalent hotspots",
        "as_of": today.date().isoformat(),
        "months": SEASON_MONTHS,
        "current_season": current_season,
        "calendar": {
            "seasons": shown,
            "counts": [[round(v, 1) for v in grid.loc[s]] for s in shown],
        },
        "seasons": [
            {
                "season": s,
                "total": round(float(totals.at[s, "h"]), 1),
                "low": round(float(totals.at[s, "h_lo"]), 1),
                "high": round(float(totals.at[s, "h_hi"]), 1),
                "kind": kind(s),
                "complete": s < current_season,
            }
            for s in shown
        ],
        "normal": normal,
        "typical": {
            "seasons_used": len(complete),
            "season_total": round(float(season_history.median()), 1) if len(complete) else 0.0,
            "peak_month": SEASON_MONTHS[peak_index],
            "start": _day_label(float(np.median(starts))) if starts else None,
            "end": _day_label(float(np.median(ends))) if ends else None,
            "worst_season": int(ranked.index[0]) if len(ranked) else None,
            "worst_total": round(float(ranked.iloc[0]), 1) if len(ranked) else 0.0,
            "quietest_season": int(ranked.index[-1]) if len(ranked) else None,
            "quietest_total": round(float(ranked.iloc[-1]), 1) if len(ranked) else 0.0,
        },
        "current": {
            "month": int(today.month),
            "through_day": int(today.day),
            "month_to_date": round(month_now, 1),
            "month_median": round(month_median, 1),
            "month_percentile": round(month_percentile),
            "month_status": _status(month_percentile),
            "season_to_date": round(season_now, 1),
            "season_to_date_median": round(float(np.median(season_to_date_history)), 1) if len(complete) else 0.0,
            "season_status": _status(_percentile(season_to_date_history, season_now)),
            "this_season_by_month": [round(v, 1) for v in grid.loc[current_season]],
        },
        "last_week": {
            "days": WEEK,
            "from": (today - pd.Timedelta(days=WEEK - 1)).date().isoformat(),
            "to": today.date().isoformat(),
            "total": round(week_now, 1),
            "median": round(float(np.median(week_history)), 1) if len(complete) else 0.0,
            "percentile": round(_percentile(week_history, week_now)),
            "status": _status(_percentile(week_history, week_now)),
            "record_total": round(record_total, 1),
            "record_from": (record_end - pd.Timedelta(days=WEEK - 1)).date().isoformat()
            if record_end is not None
            else None,
            "record_to": record_end.date().isoformat() if record_end is not None else None,
        },
    }


RAW_COLUMNS = {
    "MODIS": "modis_detections",
    "VIIRS_SNPP": "viirs_snpp_detections",
    "VIIRS_NOAA20": "viirs_noaa20_detections",
}


def calendar_table(area_rows: pd.DataFrame, today: pd.Timestamp, start: date | None, end: date | None) -> pd.DataFrame:
    """The burning calendar of one area as a flat table, one row per month, for download.

    Harmonized hotspots with their likely range, how the month compares with the median of
    the same month over complete seasons, and the raw detections of each sensor beside them.
    """
    body = summarise(area_rows, today, start, end)
    months = body["months"]
    median = dict(zip(months, body["normal"]["median"], strict=True))
    by_month = area_rows.groupby(["season", "month"])
    bounds = by_month[["h_lo", "h_hi"]].sum()
    converted = area_rows[area_rows["h_kind"] == "converted"].groupby(["season", "month"])["h"].sum()
    raw = area_rows.groupby(["season", "month", "sensor"]).size()

    records = []
    for season, counts in zip(body["calendar"]["seasons"], body["calendar"]["counts"], strict=True):
        for month, value in zip(months, counts, strict=True):
            year = season - 1 if month >= 7 else season
            if pd.Timestamp(year, month, 1) > today:
                continue
            share = float(converted.get((season, month), 0.0)) / value if value else 0.0
            in_progress = year == today.year and month == today.month
            records.append(
                {
                    "season": f"{season - 1}/{str(season)[2:]}",
                    "year": year,
                    "month": month,
                    "hotspots": round(value, 1),
                    "likely_low": round(float(bounds["h_lo"].get((season, month), 0.0)), 1),
                    "likely_high": round(float(bounds["h_hi"].get((season, month), 0.0)), 1),
                    "basis": "none"
                    if not value
                    else "converted"
                    if share > 0.99
                    else "observed"
                    if share < 0.01
                    else "mixed",
                    "median_for_month": median[month],
                    "difference_from_median": round(value - median[month], 1),
                    "month_complete": not in_progress,
                    **{column: int(raw.get((season, month, sensor), 0)) for sensor, column in RAW_COLUMNS.items()},
                }
            )
    return pd.DataFrame.from_records(records)
