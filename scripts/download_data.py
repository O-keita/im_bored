"""Download the raw inputs for the Gambia fire calendar.

Fetches, into data/raw/:
  - NASA FIRMS yearly country archives of active fire hotspots for The Gambia
    (MODIS from 2000, VIIRS S-NPP from 2012, VIIRS NOAA-20 where published)
  - geoBoundaries administrative boundaries for The Gambia (ADM0, ADM1, ADM2)
  - optionally, the current year's hotspots from the FIRMS area API, which the
    yearly archives do not cover yet (needs a free MAP_KEY in FIRMS_MAP_KEY)

Standard library only, so it runs before the virtual environment exists:
    python3 scripts/download_data.py
    FIRMS_MAP_KEY=... python3 scripts/download_data.py --recent
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

FIRMS_ARCHIVE = "https://firms.modaps.eosdis.nasa.gov/data/country/{sensor}/{year}/{sensor}_{year}_The_Gambia.csv"
FIRMS_AREA_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}/{start}"
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/GMB/{level}/"

# First year each sensor has data. Years that are not published yet are skipped.
ARCHIVE_SENSORS = {"modis": 2000, "viirs-snpp": 2012, "viirs-jpss1": 2018}

# West, south, east, north. A little wider than the country so border fires are kept.
GAMBIA_BBOX = "-16.90,13.00,-13.75,13.90"
# Standard-processing (SP) data lags by a few months and near-real-time (NRT) data only
# reaches back about two months, so the current year needs both. Where they overlap,
# the loader keeps SP.
RECENT_SOURCES = [
    "MODIS_SP", "MODIS_NRT",
    "VIIRS_SNPP_SP", "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT",
]  # fmt: skip
API_MAX_DAYS = 5

USER_AGENT = "gambia-fire-calendar/0.1 (hackathon project)"


def map_key() -> str | None:
    """The FIRMS key from the environment, or from a FIRMS_MAP_KEY line in the project's .env file."""
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "FIRMS_MAP_KEY":
                key = value.strip().strip("\"'")
    return key or None


def fetch(url: str, retries: int = 3) -> bytes | None:
    """Return the body of url, or None when the server says the file does not exist."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2 * attempt)
    return None


def download_archives(force: bool) -> None:
    this_year = dt.date.today().year
    for sensor, first_year in ARCHIVE_SENSORS.items():
        out_dir = RAW / "firms" / sensor
        out_dir.mkdir(parents=True, exist_ok=True)
        got, missing = [], []
        for year in range(first_year, this_year + 1):
            out = out_dir / f"{sensor}_{year}_The_Gambia.csv"
            if out.exists() and not force:
                got.append(year)
                continue
            body = fetch(FIRMS_ARCHIVE.format(sensor=sensor, year=year))
            if body is None or not body.startswith(b"latitude,"):
                missing.append(year)
                continue
            out.write_bytes(body)
            got.append(year)
        span = f"{got[0]} to {got[-1]} ({len(got)} files)" if got else "nothing"
        print(f"{sensor}: {span}; not published: {missing or 'none'}")


def download_boundaries(force: bool) -> None:
    out_dir = RAW / "boundaries"
    out_dir.mkdir(parents=True, exist_ok=True)
    for level in ("ADM0", "ADM1", "ADM2"):
        out = out_dir / f"gambia_{level.lower()}.geojson"
        if out.exists() and not force:
            print(f"boundaries {level}: already present")
            continue
        meta_body = fetch(GEOBOUNDARIES_API.format(level=level))
        if meta_body is None:
            print(f"boundaries {level}: not available")
            continue
        meta = json.loads(meta_body)
        body = fetch(meta["gjDownloadURL"])
        if body is None:
            print(f"boundaries {level}: download link is dead")
            continue
        out.write_bytes(body)
        (out_dir / f"gambia_{level.lower()}.meta.json").write_text(json.dumps(meta, indent=2))
        print(f"boundaries {level}: {meta.get('admUnitCount')} units, {meta.get('boundaryLicense')}")


def download_recent(year: int) -> None:
    """Pull one year of hotspots from the FIRMS area API, five days at a time."""
    key = map_key()
    if not key:
        sys.exit(
            "Set FIRMS_MAP_KEY in the environment or in .env first. Get a free key at https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        )
    out_dir = RAW / "firms" / "recent"
    out_dir.mkdir(parents=True, exist_ok=True)
    end = min(dt.date.today(), dt.date(year, 12, 31))
    for source in RECENT_SOURCES:
        header, rows = None, []
        day = dt.date(year, 1, 1)
        while day <= end:
            url = FIRMS_AREA_API.format(
                key=key, source=source, bbox=GAMBIA_BBOX, days=API_MAX_DAYS, start=day.isoformat()
            )
            body = fetch(url)
            lines = body.decode().splitlines() if body else []
            if lines and lines[0].startswith("latitude,"):
                header = header or lines[0]
                rows.extend(lines[1:])
            elif lines:
                sys.exit(f"{source} {day}: unexpected API reply: {lines[0][:200]}")
            day += dt.timedelta(days=API_MAX_DAYS)
            time.sleep(0.2)
        if header is None:
            print(f"{source}: no rows returned for {year}")
            continue
        out = out_dir / f"{source.lower()}_{year}_gambia_bbox.csv"
        out.write_text("\n".join([header, *rows]) + "\n")
        print(f"{source}: {len(rows)} hotspots in {year} (bounding box, clip to the border before use)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="download again even if the file exists")
    parser.add_argument("--recent", action="store_true", help="also pull this year's hotspots from the FIRMS API")
    parser.add_argument("--year", type=int, default=dt.date.today().year, help="year for --recent")
    args = parser.parse_args()

    download_archives(args.force)
    download_boundaries(args.force)
    if args.recent:
        download_recent(args.year)


if __name__ == "__main__":
    main()
