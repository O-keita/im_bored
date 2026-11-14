"""Put MODIS and VIIRS hotspots on one scale: VIIRS S-NPP equivalent counts.

Every hotspot gets a weight `h`. Summing `h` over any area and period gives the
harmonized count, so the same numbers work for a region, a district or a drawn shape.

  - VIIRS S-NPP detections count as 1. They are the reference.
  - Before S-NPP existed, each MODIS detection counts as the number of VIIRS detections
    it stood for during the years both flew. That number comes from a Poisson regression
    of the VIIRS count of a region and month on the MODIS count, the month and the
    region. It falls as a month gets busier: the fitted exponent on the MODIS count is
    below 1, so a month with twice the MODIS detections has less than twice the VIIRS
    ones. The predicted count of a region and month is shared equally between its MODIS
    detections, which keeps one weight per detection.
  - Before Aqua launched, only Terra flew. Those detections are first scaled up to what
    Terra and Aqua together would have seen, using the first seasons after Aqua
    launched, and then converted like any other MODIS detection. Terra's share of MODIS
    detections fell from about 45% to 40% over the record, so learning a Terra factor
    directly from the VIIRS years would overstate the early seasons.
  - After S-NPP stopped, VIIRS NOAA-20 detections continue the series, scaled by the
    ratio between the two satellites while both flew.
  - Everything else (MODIS and NOAA-20 while S-NPP was flying) gets 0, so nothing is
    counted twice.

`h_lo` and `h_hi` bound the converted values, from how far off the conversion was
when each overlap season was predicted from the others.

Two simpler conversions are kept as baselines and scored by the same test: one factor
for everything, and a factor per month scaled per region. The regression is used
because it predicts held-out seasons best at every level.

A region and month in which MODIS saw nothing stays empty. During the overlap those
held about 1% of the VIIRS detections, and the validation counts them as missed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

FIRE_MONTHS = (11, 12, 1, 2, 3, 4, 5, 6)
# Shrinks a region's own ratio toward the national one in the per-month baseline.
REGION_SHRINK = 100
# In the regression a region needs this many MODIS detections in the overlap to get its
# own effect. Banjul and Kanifing have a handful each, so they share one.
REGION_MIN_DETECTIONS = 50
POOLED = "pooled"
# FIRMS gives MODIS confidence as a percentage and VIIRS confidence as low, nominal or high.
MODIS_LOW_CONFIDENCE = 30
VIIRS_LOW_CONFIDENCE = ("l", "low")
INTERVAL = (0.1, 0.9)
# Seasons used to learn how Terra alone relates to Terra plus Aqua, counted from the
# first full season with both. The seasons after them, up to VIIRS, test it.
TERRA_FIT_SEASONS = 5
# Region-seasons with fewer reference detections than this are too noisy to judge an interval from.
MIN_FOR_INTERVAL = 50


def _month_group(month: pd.Series) -> pd.Series:
    """Fire-season months keep their own factor. July to October see almost no fire, so they share one."""
    return month.where(month.isin(FIRE_MONTHS), 0)


def _factors(train: pd.DataFrame, source: str) -> tuple[float, pd.Series, pd.Series]:
    """Overall, per-month and per-region conversion from `source` counts to VIIRS counts."""
    overall = train["viirs"].sum() / train[source].sum()
    by_month = train.groupby("mg")[["viirs", source]].sum()
    month_factor = (by_month["viirs"] / by_month[source]).replace([np.inf, np.nan], overall)
    by_region = train.groupby("region")[["viirs", source]].sum()
    region_scale = (by_region["viirs"] + REGION_SHRINK * overall) / (by_region[source] + REGION_SHRINK) / overall
    return overall, month_factor, region_scale


def _predict(rows: pd.DataFrame, source: str, factors: tuple[float, pd.Series, pd.Series]) -> np.ndarray:
    overall, month_factor, region_scale = factors
    return (
        rows[source].to_numpy()
        * rows["mg"].map(month_factor).fillna(overall).to_numpy()
        * rows["region"].map(region_scale).fillna(1.0).to_numpy()
    )


def _fit_counts(train: pd.DataFrame) -> dict:
    """Poisson regression of the VIIRS count of a region and month on its MODIS count.

    log(viirs) = month effect + region effect + exponent * log(modis), fitted on the
    cells where MODIS saw something.
    """
    cells = train[train["modis"] > 0]
    per_region = cells.groupby("region")["modis"].sum()
    own = sorted(per_region[per_region >= REGION_MIN_DETECTIONS].index)
    region = cells["region"].where(cells["region"].isin(own), POOLED)
    design = pd.concat(
        [
            np.log(cells["modis"]).rename("exponent"),
            pd.get_dummies(cells["mg"], prefix="m", dtype=float),
            # The first region is the reference: its effect is zero.
            pd.get_dummies(region, prefix="r", dtype=float).iloc[:, 1:],
        ],
        axis=1,
    )
    params = sm.GLM(cells["viirs"], design, family=sm.families.Poisson()).fit().params
    reference = min(region.unique())
    return {
        "exponent": float(params["exponent"]),
        "month": {int(k[2:]): float(v) for k, v in params.items() if k.startswith("m_")},
        "region": {reference: 0.0, **{k[2:]: float(v) for k, v in params.items() if k.startswith("r_")}},
    }


def _per_detection(model: dict, mg: pd.Series, region: pd.Series, modis: pd.Series) -> np.ndarray:
    """VIIRS detections each MODIS detection stands for, in a region and month with `modis` of them."""
    month = pd.Series(model["month"])
    regions = pd.Series(model["region"])
    fallback = regions.get(POOLED, regions.mean())
    effect = mg.map(month).fillna(month.mean()).to_numpy() + region.map(regions).fillna(fallback).to_numpy()
    count = np.maximum(modis.to_numpy(dtype=float), 1e-9)
    return np.exp(effect) * count ** (model["exponent"] - 1)


def _predict_counts(rows: pd.DataFrame, model: dict) -> np.ndarray:
    return rows["modis"].to_numpy() * _per_detection(model, rows["mg"], rows["region"], rows["modis"])


def _wape(table: pd.DataFrame, keys: list[str], column: str) -> float:
    """Weighted absolute percentage error of `column` against VIIRS, after summing to `keys`."""
    grouped = table.groupby(keys)[[column, "viirs"]].sum()
    return float((grouped[column] - grouped["viirs"]).abs().sum() / grouped["viirs"].sum())


def _fit_terra(modis: pd.DataFrame, aqua_start: pd.Timestamp, first_viirs_season: int, modis_interval) -> dict:
    """How many Terra-plus-Aqua detections one Terra detection stood for, just after Aqua launched."""
    first_full = int(fire_season_of(aqua_start))
    fit_seasons = range(first_full, first_full + TERRA_FIT_SEASONS)
    test_seasons = range(first_full + TERRA_FIT_SEASONS, first_viirs_season - 1)

    counts = modis.assign(is_terra=modis["satellite"] == "Terra").groupby(["region", "season"])
    counts = pd.DataFrame({"terra": counts["is_terra"].sum(), "modis": counts.size()}).reset_index()
    fit_rows = counts[counts["season"].isin(fit_seasons)]
    test_rows = counts[counts["season"].isin(test_seasons)].copy()
    factor = fit_rows["modis"].sum() / fit_rows["terra"].sum()
    test_rows["predicted"] = test_rows["terra"] * factor

    def wape(keys: list[str]) -> float:
        grouped = test_rows.groupby(keys)[["predicted", "modis"]].sum()
        return round(float((grouped["predicted"] - grouped["modis"]).abs().sum() / grouped["modis"].sum()), 4)

    judged = test_rows[test_rows["modis"] >= MIN_FOR_INTERVAL]
    low, high = (judged["modis"] / judged["predicted"]).quantile(list(INTERVAL))
    # The Terra years carry both steps' uncertainty. Combine them as independent errors on a log scale.
    combined = [
        float(np.exp(sign * np.hypot(np.log(step), np.log(own))))
        for sign, step, own in ((-1, low, modis_interval[0]), (1, high, modis_interval[1]))
    ]
    return {
        "terra_to_modis": round(float(factor), 3),
        "fitted_on_seasons": [fit_seasons[0], fit_seasons[-1]],
        "tested_on_seasons": [test_seasons[0], test_seasons[-1]],
        "validation": {"national_season": wape(["season"]), "region_season": wape(["region", "season"])},
        "interval": [round(combined[0], 3), round(combined[1], 3)],
    }


def fire_season_of(day: pd.Timestamp) -> int:
    return day.year + (1 if day.month >= 7 else 0)


def fit(hotspots: pd.DataFrame) -> dict:
    """Learn the conversion from the seasons both sensors observed in full, and test it."""
    modis = hotspots[hotspots["sensor"] == "MODIS"]
    snpp = hotspots[hotspots["sensor"] == "VIIRS_SNPP"]
    noaa20 = hotspots[hotspots["sensor"] == "VIIRS_NOAA20"]
    viirs_start, snpp_end = snpp["acq_date"].min(), snpp["acq_date"].max()
    aqua_start = modis.loc[modis["satellite"] == "Aqua", "acq_date"].min()

    # Complete fire seasons (July to June) seen by both S-NPP and the MODIS archive.
    first = int(snpp["season"].min()) + 1
    last = int(min(snpp["season"].max(), modis["season"].max())) - 1
    seasons = list(range(first, last + 1))

    keys = ["region", "season", "month"]
    index = pd.MultiIndex.from_product([sorted(hotspots["region"].unique()), seasons, range(1, 13)], names=keys)
    table = (
        pd.concat(
            [
                modis.groupby(keys).size().rename("modis"),
                snpp.groupby(keys).size().rename("viirs"),
            ],
            axis=1,
        )
        .reindex(index)
        .fillna(0)
        .reset_index()
    )
    table["mg"] = _month_group(table["month"])

    model: dict = {
        "unit": "VIIRS S-NPP equivalent hotspots",
        "viirs_start": viirs_start.date().isoformat(),
        "aqua_start": aqua_start.date().isoformat(),
        "snpp_end": snpp_end.date().isoformat(),
        "overlap_seasons": [first, last],
        "eras": {},
    }

    # Leave one season out: predict it from the conversion learnt on all the others.
    table["single"] = 0.0
    table["factors"] = 0.0
    table["chosen"] = 0.0
    for season in seasons:
        held_out = table["season"] == season
        factors = _factors(table[~held_out], "modis")
        table.loc[held_out, "single"] = table.loc[held_out, "modis"] * factors[0]
        table.loc[held_out, "factors"] = _predict(table[held_out], "modis", factors)
        table.loc[held_out, "chosen"] = _predict_counts(table[held_out], _fit_counts(table[~held_out]))

    by_region_season = table.groupby(["region", "season"])[["chosen", "viirs"]].sum()
    by_region_season = by_region_season[by_region_season["viirs"] >= MIN_FOR_INTERVAL]
    low, high = (by_region_season["viirs"] / by_region_season["chosen"]).quantile(list(INTERVAL))
    national = table.groupby("season")[["chosen", "viirs"]].sum()

    # The plain ratios are kept to describe the sensors. The regression does the converting.
    overall, month_factor, _ = _factors(table, "modis")
    counts = _fit_counts(table)
    empty = table["modis"] == 0
    model["eras"]["modis"] = {
        "overall_factor": round(float(overall), 3),
        "month_factor": {int(k): round(float(v), 3) for k, v in month_factor.items()},
        "count_model": {
            "exponent": round(counts["exponent"], 4),
            "month": {k: round(v, 4) for k, v in counts["month"].items()},
            "region": {k: round(v, 4) for k, v in counts["region"].items()},
        },
        "missed_where_modis_saw_nothing": round(float(table.loc[empty, "viirs"].sum() / table["viirs"].sum()), 4),
        "interval": [round(float(low), 3), round(float(high), 3)],
        "validation": {
            level: {
                "single_factor": round(_wape(table, level_keys, "single"), 4),
                "month_and_region": round(_wape(table, level_keys, "factors"), 4),
                "count_model": round(_wape(table, level_keys, "chosen"), 4),
            }
            for level, level_keys in {
                "national_season": ["season"],
                "region_season": ["region", "season"],
                "national_month": ["season", "month"],
                "region_month": ["region", "season", "month"],
            }.items()
        },
        "held_out_seasons": [
            {"season": int(s), "predicted": round(float(r["chosen"])), "observed": int(r["viirs"])}
            for s, r in national.iterrows()
        ],
    }
    model["eras"]["terra"] = _fit_terra(modis, aqua_start, first, (float(low), float(high)))

    # NOAA-20 takes over when S-NPP stops. Compare them over the seasons both saw in full.
    shared = range(int(noaa20["season"].min()) + 1, last + 1)
    both_snpp = snpp["season"].isin(shared).sum()
    both_noaa20 = noaa20["season"].isin(shared).sum()
    model["noaa20_factor"] = round(float(both_snpp / both_noaa20), 3)
    model["noaa20_overlap_seasons"] = [shared[0], shared[-1]]
    return model


def confidence_check(hotspots: pd.DataFrame) -> list[dict]:
    """Would dropping low-confidence detections make MODIS predict VIIRS any better?

    Refits the conversion with MODIS detections under 30% confidence removed, with
    low-confidence VIIRS detections removed, and with both, and reports the held-out
    error of each. Every detection is kept unless one of these clearly wins.
    """
    is_modis = hotspots["sensor"] == "MODIS"
    weak_modis = is_modis & (pd.to_numeric(hotspots["confidence"], errors="coerce") < MODIS_LOW_CONFIDENCE)
    weak_viirs = ~is_modis & hotspots["confidence"].isin(VIIRS_LOW_CONFIDENCE)
    rules = {
        "keep_all": pd.Series(False, index=hotspots.index),
        "drop_modis_low": weak_modis,
        "drop_viirs_low": weak_viirs,
        "drop_both": weak_modis | weak_viirs,
    }
    results = []
    for rule, dropped in rules.items():
        validation = fit(hotspots[~dropped])["eras"]["modis"]["validation"]
        results.append(
            {
                "rule": rule,
                "dropped_share": round(float(dropped.mean()), 4),
                **{level: errors["count_model"] for level, errors in validation.items()},
            }
        )
    return results


def apply(hotspots: pd.DataFrame, model: dict) -> pd.DataFrame:
    """Add `h`, `h_lo`, `h_hi` (the harmonized weight and its bounds) and `h_kind` to every row."""
    viirs_start = pd.Timestamp(model["viirs_start"])
    aqua_start = pd.Timestamp(model["aqua_start"])
    snpp_end = pd.Timestamp(model["snpp_end"])
    date, sensor = hotspots["acq_date"], hotspots["sensor"]
    mg = _month_group(hotspots["month"])

    h = np.zeros(len(hotspots))
    lo = np.zeros(len(hotspots))
    hi = np.zeros(len(hotspots))
    kind = np.full(len(hotspots), "unused", dtype=object)

    spec = model["eras"]["modis"]
    terra = model["eras"]["terra"]
    counts = {**spec["count_model"], "month": {int(k): v for k, v in spec["count_model"]["month"].items()}}
    # How many Terra-plus-Aqua detections each MODIS row stands for, then the size of its
    # region and month in those units. The whole month is counted, including the days
    # after VIIRS started, so that a month split by a launch is not treated as a quiet one.
    is_modis = sensor == "MODIS"
    units = pd.Series(np.where(is_modis & (date < aqua_start), terra["terra_to_modis"], 1.0), index=hotspots.index)
    units = units.where(is_modis, 0.0)
    in_cell = units.groupby([hotspots["region"], hotspots["season"], hotspots["month"]]).transform("sum")
    modis_weight = units.to_numpy() * _per_detection(counts, mg, hotspots["region"], in_cell)
    for in_era, interval in (
        (is_modis & (date < aqua_start), terra["interval"]),
        (is_modis & (date >= aqua_start) & (date < viirs_start), spec["interval"]),
    ):
        mask = in_era.to_numpy()
        h[mask] = modis_weight[mask]
        lo[mask], hi[mask] = h[mask] * interval[0], h[mask] * interval[1]
        kind[mask] = "converted"

    observed = ((sensor == "VIIRS_SNPP") & (date >= viirs_start)).to_numpy()
    h[observed] = lo[observed] = hi[observed] = 1.0
    kind[observed] = "observed"

    successor = ((sensor == "VIIRS_NOAA20") & (date > snpp_end)).to_numpy()
    h[successor] = lo[successor] = hi[successor] = model["noaa20_factor"]
    kind[successor] = "observed"

    return hotspots.assign(h=h, h_lo=lo, h_hi=hi, h_kind=kind)
