# Plan of action

Written Saturday 14 November 2026, 15:00 GMT. Project submission closes on Sunday 15 November at 11:59 p.m. in the time zone of your Local Event (or of the Team Owner's residence for the Universal Event). Your Local Lead may set an earlier time for local judging, so ask.

## Rules that affect the build

Checked on 14 November against the official Participant Terms and Conditions, the Participant FAQs and the Project Submission Guide.

- **NASA data is required, other data is allowed.** To be eligible for a Global Award "you must use at least one NASA data or resource". Non-NASA data and code are permitted if they are "freely and publicly available without restriction or, at a minimum, are also licensed as open source". Space Agency Partner data is encouraged.
- **What that means here.** FIRMS is NASA Earthdata and is the one resource the challenge's Resources tab lists, so the core of the project is safe. The only non-NASA input is the geoBoundaries district shapes, which are public under CC BY 4.0. That license requires attribution, so cite it. If you want zero doubt, the app also works without it: the challenge only asks for a drawn or typed area of interest.
- **Cite everything.** Every dataset, library, image and piece of code must be listed on the submission form, "even if it is open source or freely available". NASA can remove awards from teams that do not.
- **Declare AI use.** The site calls it Super Intelligence (SI) this year. AI tools are allowed to speed up the work but should not be used to come up with the idea, and the submission must say where and how they were used. Generated content must not use NASA logos or mission identifiers.
- **Your work becomes open.** Original content must be freely available or under an OSI license. If you name none, NASA distributes it under Apache 2.0.
- **The submission form asks for:** a high-level summary, a demo (a video of 30 seconds or less, or a deck of at most 7 slides) at a public link, a public link to the final project, project details, the AI use statement, the NASA data used, and other references. Links must open without a login.

## What the challenge asks for

From the official statement, the judges expect two parts:

1. **Harmonization.** Combine the long MODIS record with the more detailed VIIRS record so that "the sensor of origin no longer matters".
2. **A web application** that takes the harmonized data, lets a user pick an area and a date range, and shows a burning activity calendar from the early 2000s to now.

Things the statement suggests and we will include: comparison of the current month against the historical median, anomalies against multi-year averages, accessible color ramps, an interactive area selector (draw on a map or enter latitude and longitude), and a downloadable CSV of the hotspots in a search.

The only resource the statement lists is NASA FIRMS, which is what we use.

## Data sources

| Source | What it gives | Coverage | Access | Status |
|---|---|---|---|---|
| FIRMS MODIS C6.1 country archive | Hotspots at 1 km, Terra and Aqua | Nov 2000 to Dec 2025 | Direct CSV, no key | Downloaded, 25,381 rows |
| FIRMS VIIRS S-NPP country archive | Hotspots at 375 m | Jan 2012 to Dec 2025 | Direct CSV, no key | Downloaded, 71,014 rows |
| FIRMS VIIRS NOAA-20 country archive | Hotspots at 375 m | Apr 2018 to Dec 2025 | Direct CSV, no key | Downloaded, 40,811 rows |
| FIRMS area API | The same sensors for 2026 | Jan 2026 to today | Free MAP_KEY, 5 days per request | Downloaded, 11,907 rows inside the border |
| geoBoundaries GMB | Country, 8 regions, 48 districts | 2020 boundaries | Direct GeoJSON, CC BY 4.0 | Downloaded |

Archive URL pattern: `https://firms.modaps.eosdis.nasa.gov/data/country/<sensor>/<year>/<sensor>_<year>_The_Gambia.csv`, with sensor one of `modis`, `viirs-snpp`, `viirs-jpss1`.

Optional, only if time allows: NASA POWER daily rainfall (no key) to explain early or late seasons, and the MODIS MCD64A1 burned area product as an independent check on the calendar.

## What the data already tells us

These come from a first pass over the downloaded files and shape the method.

- **The season is sharp.** More than 99% of detections fall between November and June, peaking in February and March. July to October is close to zero. So the calendar should use a fire season running July to June, not the calendar year. `firecal.data.fire_season` already does this.
- **VIIRS sees about five times more.** Over 2012 to 2025, VIIRS S-NPP records 4.7 to 6.4 times as many hotspots per year as MODIS (Terra and Aqua together), 5.3 on average. Against Aqua alone, which passes at a similar time of day, the ratio is 7.8 to 10.5.
- **The ratio changes through the season.** It is about 4.3 in November and 6.5 in May. A single scaling factor would distort the shape of the season, so the correction has to depend on the month at least.
- **Two edge cases in MODIS.** The year 2000 is partial (the record starts 6 November), and Aqua only starts in mid 2002, so 2000 to 2002 is Terra only and needs its own factor.
- **The two VIIRS satellites agree.** From 2019 on, NOAA-20 and S-NPP yearly counts are within about 5% of each other. That makes NOAA-20 a safe continuation now that S-NPP has stopped.
- **S-NPP has stopped.** In the 2026 pull, the last VIIRS S-NPP detection is 1 November 2026, while NOAA-20 and MODIS run to today. That matches the report that S-NPP delivery ended on that date. From November 2026 the current season has to come from NOAA-20, so the harmonized target should be defined so that NOAA-20 can stand in for S-NPP.
- **2026 has a quiet gap.** Standard-quality data ends in July and the near-real-time feed only reaches back to mid September or October, so August to early October 2026 is missing. That is the wet season, when almost nothing burns, but say so in the app.
- **Almost everything is a vegetation fire.** Fewer than 0.3% of rows are flagged as static sources or offshore, and the loader drops them.

## Method in one paragraph

Express everything in VIIRS S-NPP equivalent hotspot counts. Aggregate each sensor to district by month. On the overlap years (2012 to 2025), fit a count model that predicts the VIIRS count from the MODIS count, the month and the region. Apply it to 2000 to 2011 to backfill the series, use observed VIIRS from 2012 on, and carry a prediction interval so the app can show how sure the backfill is. Prove it works by leaving out one overlap season at a time and predicting it from MODIS alone.

## Milestones

### M0. Setup and data (done)

- Repository, dependencies, download script, raw data, shared loader.

### M1. Clean and aggregate (done)

- 2026 pulled from the FIRMS API with standard-quality rows preferred over near-real-time ones.
- Every hotspot clipped to within 1 km of the border and tagged with its region and district: 148,247 rows from 6 November 2000 to 14 November 2026, in `data/processed/hotspots.parquet`.
- The confidence rule is decided: keep every detection. Dropping MODIS rows under 30, VIIRS low-confidence rows, or both was tested with the hidden-season test and each made the prediction slightly worse (region and season error 9.9% with everything kept, 10.7% with both dropped). The low-confidence share is also steady from season to season (about 4% of MODIS, 17% of VIIRS), so it does not bend the series. The numbers are in `harmonization.json` under `confidence_check`.

### App skeleton (done)

- FastAPI backend with area and date selection (country, region, district, circle, polygon), calendar counts, map points and CSV download. 18 tests pass.
- React and Vite frontend with the area selector, date range, map, calendar heatmap in the cividis ramp and the CSV button.
- The calendar shows the harmonized series, with converted seasons marked.

### M2. Harmonize (done)

- Three conversions were scored by hiding one overlap season at a time (2012/13 to 2025/26) and predicting it from MODIS alone: one factor for everything, a factor per month scaled per region, and a Poisson regression of the VIIRS count on the MODIS count, month and region. The regression wins at every level and is the one in use.

| Conversion | Country, season | Region, season | Country, month | Region, month |
|---|---|---|---|---|
| One factor for everything | 6.7% | 14.4% | 15.1% | 27.4% |
| A factor per month, scaled per region | 7.3% | 11.7% | 14.4% | 26.2% |
| Poisson count regression (used) | 5.4% | 9.9% | 12.8% | 23.5% |

- The regression's exponent on the MODIS count is 0.79: busy months convert at a lower rate. A fixed ratio cannot do that, which is why it overshot heavy seasons such as 2023/24.
- Terra-only years (before August 2002) are first scaled by 2.233 to Terra plus Aqua, fitted on 2002/03 to 2006/07 and tested on 2007/08 to 2010/11 (2.8% off nationally).
- NOAA-20 continues the series after S-NPP stopped, at a factor of 1.007.
- Every hotspot carries a weight `h` with bounds `h_lo` and `h_hi` and a kind (`observed`, `converted` or `unused`), so district, region and drawn-area totals all come from the same column.
- The app shows the raw record of each satellite beside the harmonized one for the selected area, and the validation table, under "How 26 years became one record".
- Continuity: no step at January 2012 in the national series (2010/11 is 6,391, 2011/12 is 5,309, 2012/13 is 5,004), and the ratio of VIIRS to MODIS shows no trend over the overlap (4.8 to 6.5 per season).
- Not checked: the two Terra-only seasons are the heaviest in the record (about 7,850 and 7,430). Terra's raw counts are high in those seasons too, and their confidence, night share and fire power look like later Terra data, so it is not a conversion artefact. Whether burning really was that heavy needs an independent check such as MCD64A1 burned area.

### M3. Calendar and anomalies (Sunday morning, 2 hours)

- Calendar matrix per area: seasons down, months across, harmonized count in each cell.
- Per area and month: historical median and percentiles. Current month compared with the median, as a ratio and a percentile rank.
- Season markers: start date (when 10% of a typical season's hotspots have occurred), peak month, end date. Flag seasons that start early or run heavy.
- Done when: a function takes an area and a date range and returns the calendar, the anomaly figures and the hotspot rows.

### M4. Finish the web application (Sunday, 3 hours)

The skeleton runs end to end. What is left:

- Serve the harmonized calendar from M2 and the anomaly figures from M3, with backfilled seasons marked.
- Add the views the statement asks for: season totals over time, and the current month against the historical median.
- Add a draw-a-polygon tool on the map. The API already accepts polygons.
- Done on 14 November: light theme with a checked color ramp, calendar CSV export, save-as-PDF, a last-7-days comparison against earlier seasons and the record week, and a message when a drawn area is outside The Gambia.
- Mark 2026 as provisional and note the August to October gap.
- Open it in a browser on a laptop and a phone and fix what looks wrong. So far it has only been checked by building it and calling the API through the dev server.
- Done when: a person who has never seen it can pick a region, read off the worst season and the usual peak month, and download the CSV.

### M5. Local-language briefing (Sunday, 1 to 2 hours, stretch)

- A short plain-language summary of the selected area: when burning usually starts, whether this month is above or below normal, and what the last heavy season was.
- English first, then Wolof and Mandinka. You write the sentence templates as a native speaker and the app fills in the numbers. No model is needed for this, which keeps the output accurate.
- Done when: the three versions read naturally to you and the numbers match the charts.

### M6. Submit (Sunday evening, 2 hours)

- Deploy the API to a Python host such as Render, Railway or Fly.io, and the React build to Vercel or Netlify with `/api` rewritten to the API. Free Python hosts sleep when idle, so open the app shortly before judging, or serve the built frontend from FastAPI so there is one service to keep awake.
- Make the repository public on GitHub and add a license file (Apache 2.0 is the default NASA applies).
- Record a demo video of 30 seconds or less, or build a deck of at most 7 slides: the problem in Gambian terms, the harmonization chart, the app. Host it at a link that opens without a login.
- Fill in the project page: summary, method, validation numbers, the NASA data used (FIRMS MODIS and VIIRS), other references (geoBoundaries, every library), and the statement of where AI tools were used.
- Save the project page early and often, and submit well before 11:59 p.m. You can keep editing until the deadline.
- Done when: the project is submitted with a public repository link and a working demo link.

## If time runs short

Cut in this order: M5, the draw-a-polygon tool, the regression model (ship the monthly ratio baseline with its validation numbers). Do not cut the validation table or the CSV download; the first is the evidence for the harmonization and the second is asked for in the statement.

## Risks

- **Small counts per district.** Some of the 48 districts have very few MODIS hotspots in a month, which makes a per-district ratio noisy. Fit the model at region level and apply it to districts.
- **MODIS sensitivity drift.** If the ratio trends over 2012 to 2025, a fixed correction will bias the early years. Plot the ratio by year before trusting it.
- **Near-real-time rows differ slightly from the archive.** The 2026 rows have no `type` column and may be revised. Mark 2026 as provisional in the app.
