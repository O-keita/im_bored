"""Download NASA tree cover and land cover rasters for The Gambia.

Asks NASA AppEEARS for two yearly MODIS products, cut to The Gambia, and saves the
GeoTIFFs into data/raw/landcover/:
  - MOD44B v6.1, layer Percent_Tree_Cover: percent of each 250 m pixel under trees
    (0 to 100, fill value 253)
  - MCD12Q1 v6.1, layer LC_Type1: IGBP land cover class of each 500 m pixel
    (fill value 255)

There is no API key. AppEEARS needs a free NASA Earthdata Login, from
https://urs.earthdata.nasa.gov/users/new. Put the username and password in the
environment or in .env as EARTHDATA_USERNAME and EARTHDATA_PASSWORD.

The request is queued on NASA's side, so the script submits it, waits, then downloads.
The task id is kept in data/raw/landcover/task.json: if the script is stopped while
waiting, run it again and it picks the same request up instead of sending a new one.

Standard library only:
    python3 scripts/download_tree_cover.py
    python3 scripts/download_tree_cover.py --start 2012 --end 2024
    python3 scripts/download_tree_cover.py --outline     # cut to the border, not the box
    python3 scripts/download_tree_cover.py --no-wait     # submit and exit
    python3 scripts/download_tree_cover.py --new         # forget the saved request
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "landcover"
TASK_FILE = OUT / "task.json"
OUTLINE = ROOT / "data" / "raw" / "boundaries" / "gambia_adm0.geojson"

API = "https://appeears.earthdatacloud.nasa.gov/api"
LAYERS = [
    {"product": "MOD44B.061", "layer": "Percent_Tree_Cover"},
    {"product": "MCD12Q1.061", "layer": "LC_Type1"},
]

# West, south, east, north. The same box as the FIRMS download, a little wider than
# the country so pixels on the border are kept.
WEST, SOUTH, EAST, NORTH = -16.90, 13.00, -13.75, 13.90

FIRST_YEAR = 2000
POLL_SECONDS = 30
USER_AGENT = "gambia-fire-calendar/0.1 (hackathon project)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop urllib following redirects, so the login token is never sent on to the file store."""

    def redirect_request(self, *args, **kwargs):
        return None


def setting(name: str) -> str | None:
    """A value from the environment, or from a NAME=value line in the project's .env file."""
    value = os.environ.get(name, "").strip()
    env_file = ROOT / ".env"
    if not value and env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, found = line.partition("=")
            if key.strip() == name:
                value = found.strip().strip("\"'")
    return value or None


def call(method: str, path: str, token: str | None = None, body: dict | None = None, basic: str | None = None) -> dict:
    """One JSON request to the AppEEARS API. Exits with the server's message on an error."""
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if basic:
        headers["Authorization"] = f"Basic {basic}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif method == "POST":
        data = b""
    request = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        sys.exit(f"{method} {path} failed with HTTP {error.code}: {detail}")


def login() -> str:
    username = setting("EARTHDATA_USERNAME")
    password = setting("EARTHDATA_PASSWORD")
    if not username or not password:
        sys.exit(
            "Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD in the environment or in .env first. "
            "Create a free account at https://urs.earthdata.nasa.gov/users/new"
        )
    basic = base64.b64encode(f"{username}:{password}".encode()).decode()
    return call("POST", "/login", basic=basic)["token"]


def area(outline: bool) -> dict:
    """The area to cut to, as GeoJSON in longitude and latitude."""
    if outline:
        shape = json.loads(OUTLINE.read_text())
        return {"type": "FeatureCollection", "features": shape["features"]}
    ring = [[WEST, SOUTH], [EAST, SOUTH], [EAST, NORTH], [WEST, NORTH], [WEST, SOUTH]]
    box = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [ring]}}
    return {"type": "FeatureCollection", "features": [box]}


def submit(token: str, start: int, end: int, outline: bool) -> str:
    task = {
        "task_type": "area",
        "task_name": f"gambia_landcover_{start}_{end}",
        "params": {
            "dates": [{"startDate": f"01-01-{start}", "endDate": f"12-31-{end}"}],
            "layers": LAYERS,
            "geo": area(outline),
            "output": {"format": {"type": "geotiff"}, "projection": "geographic"},
        },
    }
    reply = call("POST", "/task", token=token, body=task)
    task_id = reply["task_id"]
    TASK_FILE.write_text(json.dumps({"task_id": task_id, "start": start, "end": end, "outline": outline}, indent=2))
    print(f"submitted request {task_id} for {start} to {end}")
    return task_id


def wait(token: str, task_id: str) -> None:
    last = None
    while True:
        status = call("GET", f"/task/{task_id}", token=token).get("status")
        if status != last:
            print(f"request {task_id}: {status}")
            last = status
        if status == "done":
            return
        if status == "error":
            sys.exit(f"NASA reported an error for request {task_id}. Run again with --new to send a fresh one.")
        time.sleep(POLL_SECONDS)


def download(token: str, task_id: str, force: bool) -> None:
    files = call("GET", f"/bundle/{task_id}", token=token).get("files", [])
    opener = urllib.request.build_opener(NoRedirect)
    saved = skipped = 0
    for entry in files:
        out = OUT / Path(entry["file_name"]).name
        if out.exists() and not force:
            skipped += 1
            continue
        request = urllib.request.Request(
            f"{API}/bundle/{task_id}/{entry['file_id']}",
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        )
        try:
            with opener.open(request, timeout=120) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location")
            if error.code not in (301, 302, 303, 307) or not location:
                sys.exit(f"{entry['file_name']}: download failed with HTTP {error.code}")
            # The redirect points at a signed link that carries its own permission.
            plain = urllib.request.Request(location, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(plain, timeout=300) as response:
                body = response.read()
        out.write_bytes(body)
        saved += 1
    rasters = sorted(path.name for path in OUT.glob("*.tif"))
    print(f"saved {saved} files, {skipped} already present, {len(rasters)} rasters in {OUT.relative_to(ROOT)}")
    if rasters:
        print(f"first: {rasters[0]}")
        print(f"last:  {rasters[-1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=int, default=FIRST_YEAR, help="first year to ask for")
    parser.add_argument("--end", type=int, default=dt.date.today().year, help="last year to ask for")
    parser.add_argument("--outline", action="store_true", help="cut to the country border instead of the bounding box")
    parser.add_argument("--no-wait", action="store_true", help="submit the request and exit without waiting")
    parser.add_argument("--new", action="store_true", help="send a new request even if one is saved")
    parser.add_argument("--force", action="store_true", help="download again even if the file exists")
    args = parser.parse_args()
    if args.start > args.end:
        sys.exit("--start must not be after --end")

    OUT.mkdir(parents=True, exist_ok=True)
    token = login()
    if TASK_FILE.exists() and not args.new:
        task_id = json.loads(TASK_FILE.read_text())["task_id"]
        print(f"picking up saved request {task_id}")
    else:
        task_id = submit(token, args.start, args.end, args.outline)
    if args.no_wait:
        print("not waiting; run the script again later to download")
        return
    wait(token, task_id)
    download(token, task_id, args.force)


if __name__ == "__main__":
    main()
