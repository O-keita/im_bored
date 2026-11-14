# Gambia Fire Calendar

A harmonized MODIS and VIIRS burning activity calendar for The Gambia, built for the NASA Space Apps Challenge 2026 challenge [Harmonization of MODIS and VIIRS Hot Spots](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/).

Bushfires burn across Gambian farmland, community forests and rangeland every dry season. Satellites have recorded them since 2000, but the record is split between two sensors that cannot be compared directly. This project merges them into one consistent series per region and district, so a forestry officer can see when burning normally starts and peaks, and whether this month is unusual.

The plan, data sources and milestones are in [PLAN.md](PLAN.md).

## How the two records are joined

Everything is expressed in VIIRS S-NPP equivalent hotspots. From 20 January 2012 the series is what S-NPP counted. Before that, MODIS detections are converted with a Poisson regression of the VIIRS count of a region and month on the MODIS count, the month and the region, fitted on the 14 fire seasons both sensors saw in full (2012/13 to 2025/26). The fitted exponent on the MODIS count is 0.79, so the conversion rate falls in busy months. Each region and month's predicted count is shared equally between its MODIS detections, which gives every hotspot one weight and lets any drawn area add up.

Before Aqua launched in August 2002 only Terra flew. Those detections are first scaled by 2.233 to what Terra and Aqua together would have seen (tested on 2007/08 to 2010/11: 2.8% off on national season totals). After S-NPP stopped on 1 November 2026, NOAA-20 carries the series, scaled by 1.007.

The test: hide one overlap season, fit on the other 13, predict the hidden one from MODIS alone. Average absolute error as a share of what VIIRS counted:

| Conversion | Country, season | Region, season | Country, month | Region, month |
|---|---|---|---|---|
| One factor for everything | 6.7% | 14.4% | 15.1% | 27.4% |
| A factor per month, scaled per region | 7.3% | 11.7% | 14.4% | 26.2% |
| Poisson count regression (used) | 5.4% | 9.9% | 12.8% | 23.5% |

Every detection is kept whatever its confidence. Dropping low-confidence rows was tested with the same hidden-season test and never helped:

| Rule | Rows dropped | Country, season | Region, season |
|---|---|---|---|
| Keep every detection (used) | 0.0% | 5.4% | 9.9% |
| Drop MODIS under 30% confidence | 0.7% | 5.5% | 10.0% |
| Drop low-confidence VIIRS | 14.1% | 5.5% | 10.5% |
| Drop both | 14.8% | 5.8% | 10.7% |

Limits worth knowing. A region and month in which MODIS saw nothing stays empty, and those held 1.0% of VIIRS detections during the overlap. The two Terra-only seasons (2000/01 and 2001/02) come out as the heaviest in the record. That is in Terra's own raw counts (741 and 693 detections, against 346 the season after), not something the conversion adds, but it has not been checked against an independent product such as MCD64A1 burned area.

The code is in `src/firecal/harmonize.py`, and the fitted numbers are written to `data/processed/harmonization.json` on every build.

## Scope and accessibility

The tool covers The Gambia only. Every area a user picks or draws is read from the record inside the border, and an area outside it comes back empty with a message saying so. The method does not depend on the country: FIRMS publishes the same yearly archives for every country, so it can be refitted elsewhere, but the conversion factors here were learnt from Gambian fires and should not be reused as they are.

A single fire is not tracked as an object. To compare burning now with earlier burning, the page shows the last 7 days in the selected area against the same 7 days of every earlier season, and against the busiest 7 days on record there. Draw a shape around a fire to compare that place with its own history.

Three things can be downloaded for any selection: every hotspot as a CSV, the harmonized calendar as a CSV, and the whole page as a PDF through the browser's print dialog.

Colors were checked with a script, not by eye. The calendar ramp is one orange hue in seven steps from light to dark, each 0.08 darker than the last in OKLCH lightness, and the palest step has 2.15:1 contrast against the page, so the order survives colorblindness and greyscale printing. The three sensor lines (blue, green, pink) stay at least 13 apart in OKLab distance under simulated protanopia and deuteranopia, where 8 is the target. The pink NOAA-20 line is below 3:1 contrast against the page, so it is also dashed and named in the legend and tooltip. Every chart has its numbers available as text: the calendar has a table view and each chart shows values on hover.

## Setup

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20 and pnpm.

```bash
uv sync
python3 scripts/download_data.py --recent
uv run python scripts/build_dataset.py
cd web && pnpm install
```

`download_data.py` fetches about 12 MB: 26 years of MODIS hotspots, 14 of VIIRS S-NPP, 8 of VIIRS NOAA-20, and the country, region and district boundaries. `--recent` adds the current year from the FIRMS API, which the yearly archives do not cover yet. It needs a free key from <https://firms.modaps.eosdis.nasa.gov/api/map_key/>, read from the `FIRMS_MAP_KEY` environment variable or a `FIRMS_MAP_KEY=` line in `.env`.

`build_dataset.py` clips everything to the border, tags each hotspot with its region and district, fits the harmonization, and writes `data/processed/hotspots.parquet` and `harmonization.json`, which the API serves.

## Run

Two terminals:

```bash
uv run uvicorn firecal.api:app --reload --port 8010
```

```bash
cd web && pnpm dev
```

Open <http://localhost:5173>. The dev server forwards `/api` to port 8010. Interactive API docs are at <http://localhost:8010/docs>.

## Check

```bash
uv run pytest
uv run ruff check src scripts tests
cd web && pnpm build && pnpm lint
```

## API

| Endpoint | Returns |
|---|---|
| `GET /api/health` | Row count and date range of the record |
| `GET /api/areas` | The 8 regions and the districts in each |
| `GET /api/boundaries/{adm0,adm1,adm2}` | GeoJSON outlines |
| `GET /api/method` | The fitted harmonization, its validation errors and the confidence check |
| `POST /api/calendar` | Raw hotspot counts per sensor, fire season and month |
| `POST /api/summary` | The harmonized calendar, season totals, the normal season and how this month compares |
| `POST /api/hotspots` | Points for the map, thinned to 8,000 |
| `POST /api/hotspots.csv` | Every hotspot in the selection as a CSV |
| `POST /api/calendar.csv` | The harmonized calendar as a CSV: one row per month with its likely range, the median for that month, the difference from it, and each sensor's raw detections |

The five `POST` endpoints take the same body: an `area` (`country`, `region`, `district`, `circle` or `polygon`) and optional `start` and `end` dates.

## Layout

```
scripts/download_data.py   fetches FIRMS archives, boundaries and current-year hotspots
scripts/build_dataset.py   clips to the border, assigns districts, writes the Parquet table
src/firecal/data.py        loads the raw files and the cleaned table
src/firecal/harmonize.py   fits and applies the MODIS to VIIRS conversion, with its validation
src/firecal/query.py       area and date selection, raw counts per sensor
src/firecal/summary.py     harmonized calendar, normal season and anomalies for one area
src/firecal/api.py         FastAPI app
tests/                     API tests against the real table
web/                       React and Vite frontend (map, area selector, calendar heatmap)
data/raw/                  FIRMS CSVs and geoBoundaries GeoJSON
data/processed/            hotspots.parquet, harmonization.json, areas.json
```

## Data credits

- Active fire hotspots: NASA FIRMS (MODIS Collection 6.1, VIIRS S-NPP and NOAA-20 375 m).
- Boundaries: geoBoundaries, CC BY 4.0.
- Base map: OpenStreetMap contributors, ODbL.
