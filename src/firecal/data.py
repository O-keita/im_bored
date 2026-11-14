"""Load FIRMS hotspots into one table with a shared schema."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_FIRMS = ROOT / "data" / "raw" / "firms"
BOUNDARIES = ROOT / "data" / "raw" / "boundaries"
PROCESSED = ROOT / "data" / "processed"

# Yearly country archives: folder name -> sensor label used everywhere else.
ARCHIVE_SENSORS = {"modis": "MODIS", "viirs-snpp": "VIIRS_SNPP", "viirs-jpss1": "VIIRS_NOAA20"}
# Current-year API pulls: file prefix -> sensor label. Each has an `_sp` and an `_nrt` file.
RECENT_SENSORS = {"modis": "MODIS", "viirs_snpp": "VIIRS_SNPP", "viirs_noaa20": "VIIRS_NOAA20"}

# FIRMS `type` 0 is a presumed vegetation fire. 1 is a volcano, 2 another static
# land source such as a gas flare, 3 an offshore detection.
VEGETATION_FIRE = 0

COLUMNS = [
    "sensor", "source", "satellite", "latitude", "longitude", "acq_date", "acq_time",
    "daynight", "confidence", "frp", "brightness", "type",
]  # fmt: skip


def fire_season(dates: pd.Series) -> pd.Series:
    """Season label for each date. Burning runs November to June, so a season spans
    two calendar years: July 2022 to June 2023 is season 2023."""
    return dates.dt.year + (dates.dt.month >= 7).astype(int)


def _read(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"confidence": str, "acq_time": str})
    # MODIS calls its fire channel `brightness`, VIIRS `bright_ti4`. They are different
    # channels and are not comparable across sensors.
    frame = frame.rename(columns={"bright_ti4": "brightness"})
    frame["acq_date"] = pd.to_datetime(frame["acq_date"])
    return frame


def _load_archives() -> list[pd.DataFrame]:
    frames = []
    for folder, sensor in ARCHIVE_SENSORS.items():
        files = sorted((RAW_FIRMS / folder).glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"No files in {RAW_FIRMS / folder}. Run scripts/download_data.py first.")
        frame = pd.concat((_read(f) for f in files), ignore_index=True)
        frames.append(frame.assign(sensor=sensor, source="archive"))
    return frames


def _load_recent(after: dict[str, pd.Timestamp]) -> list[pd.DataFrame]:
    """Current-year rows from the API. Standard-processing rows win; near-real-time rows
    are only kept for dates after the last standard-processing date. Near-real-time
    rows have no `type` column and are treated as vegetation fires."""
    frames = []
    for prefix, sensor in RECENT_SENSORS.items():
        last = after[sensor]
        for quality in ("sp", "nrt"):
            for path in sorted((RAW_FIRMS / "recent").glob(f"{prefix}_{quality}_*.csv")):
                frame = _read(path)
                frame = frame[frame["acq_date"] > last]
                if frame.empty:
                    continue
                if "type" not in frame:
                    frame = frame.assign(type=VEGETATION_FIRE)
                frames.append(frame.assign(sensor=sensor, source=quality))
                last = max(last, frame["acq_date"].max())
    return frames


def load_raw_hotspots(vegetation_only: bool = True) -> pd.DataFrame:
    """Every downloaded hotspot, one row per detection, before clipping to the border.

    Archive rows are already limited to The Gambia. Current-year rows cover a bounding
    box and include Senegal; scripts/build_dataset.py clips them.
    """
    archives = _load_archives()
    last_archive_date = {frame["sensor"].iat[0]: frame["acq_date"].max() for frame in archives}
    hotspots = pd.concat([*archives, *_load_recent(last_archive_date)], ignore_index=True)[COLUMNS]
    if vegetation_only:
        hotspots = hotspots[hotspots["type"] == VEGETATION_FIRE]
    hotspots = hotspots.assign(
        year=hotspots["acq_date"].dt.year,
        month=hotspots["acq_date"].dt.month,
        season=fire_season(hotspots["acq_date"]),
    )
    return hotspots.reset_index(drop=True)


@lru_cache(maxsize=1)
def load_hotspots() -> pd.DataFrame:
    """The cleaned table built by scripts/build_dataset.py: inside the border, with
    `region` and `district` on every row. Cached, so treat the result as read-only."""
    path = PROCESSED / "hotspots.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing. Run scripts/build_dataset.py first.")
    return pd.read_parquet(path)
