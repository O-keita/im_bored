# Gambia Fire Calendar: presentation draft

Written 14 November 2026. Seven slides, because the Space Apps submission allows a deck of at most 7. Each slide has the text to put on it, a suggested visual, and what to say. The research on The Gambia that backs slide 2 and slide 7 is at the end, with sources and a list of what could not be verified.

Every number about the project comes from `data/processed/harmonization.json` and the API as built on 14 November. If you rebuild the data, check them again.

## Slide 1. Title

**On the slide**

- Gambia Fire Calendar
- Twenty-six years of satellite fire detections over The Gambia, joined into one record that a forestry officer can read month by month.
- NASA Space Apps Challenge 2026 · Harmonization of MODIS and VIIRS Hot Spots
- Three figures along the bottom:
  - 148,247 hotspots from three NASA sensors, November 2000 to November 2026
  - 1 scale for all of them: VIIRS-equivalent hotspots
  - 5.4% average error when a hidden season is predicted from the older sensor alone

**Visual:** `app-overview.png` (the map with hotspots and the five tiles), or the map alone.

**Say:** This is a tool for The Gambia. Every dry season the bush burns, and satellites have watched it since November 2000. The three numbers are the whole talk in short: how much data there is, that it is now on one scale, and how well the conversion holds.

## Slide 2. The problem, in Gambian terms

**On the slide**

- Every dry season, the Gambian bush burns.
- In 2001 the Forestry Department wrote that "most of the country's forest lands are burnt annually".
- The causes it listed are still the ones named today: field clearing, hunting, honey collection, herding, fuelwood collection and smoking.
- Three short points:
  - December 2025, Jamali Babou, Central River Region: a wind-driven fire took a family's home and its whole harvest of groundnut, maize, millet and rice.
  - May 2026: the Department of Forestry said the Lower River Region records the highest rate of bush fires in the country.
  - Satellites could say when burning starts in each district and whether this month is unusual. The record exists, but it is split in two.

**Visual:** a photograph of your own from a burnt field or a fire belt, if you have one. Do not use a news photograph without permission.

**Say:** Fire here is mostly started by people and mostly in the dry season, and the losses are personal: a house, a year of food, a cashew orchard. Forestry officers know the season from experience. What they do not have is one record that says when burning normally starts in their district and whether this month is out of the ordinary. Keep the Lower River Region statement in mind; our numbers agree with it on the last slide.

**Sources on the slide:** Dampha, Forestry Department, for FAO (2001); The Point, 19 December 2025 and 14 May 2026.

## Slide 3. Why the record cannot be read as it stands

**On the slide**

- Two sensors, two different counts of the same fires.
- MODIS, on Terra and Aqua: 1 km squares, watching since November 2000. 26,295 detections over The Gambia.
- VIIRS, on S-NPP and NOAA-20: 375 m squares, watching since January 2012. It sees small fires that MODIS misses: 75,846 detections from S-NPP alone.
- ×5.3: VIIRS detections for each MODIS detection over the same seasons. Read raw, burning seems to jump fivefold in 2012.
- The gap is not one number. It is about ×4.2 in November and ×6.3 in May, and it narrows in the busiest months.

**Visual:** the left half of `two-records.png` (what each satellite counted per season).

**Say:** If you plot the raw counts, it looks as if fires in The Gambia became five times more common in 2012. They did not. The instrument changed. And because the ratio moves with the month and with how busy the month is, multiplying by one factor would bend the shape of the season.

## Slide 4. The harmonization

**On the slide**

- One unit: VIIRS-equivalent hotspots.
- From 2012: count what VIIRS S-NPP saw. It is the reference.
- 2002 to 2012: convert MODIS with a Poisson regression on its count, the month and the region, fitted on the 14 seasons both sensors watched.
- Before August 2002: only Terra flew, so its detections are first scaled by ×2.23 to what Terra and Aqua would have seen.
- After 1 November 2026: S-NPP stopped. NOAA-20 carries the record on at a factor of 1.007.
- Every hotspot carries one weight, so a district, a region or a shape drawn by hand all add up from the same column.

**Visual:** `two-records.png` in full: raw counts on the left, one continuous record on the right with the likely range shaded.

**Say:** Four eras, one unit. VIIRS S-NPP is the reference because it has the detail and a fourteen-season overlap with MODIS. The regression's exponent on the MODIS count is 0.81, below one, so busy months convert at a lower rate: where MODIS counts twice as many fires, VIIRS counts about 1.7 times as many. The Terra factor was fitted on 2002/03 to 2006/07 and tested on 2007/08 to 2010/11, where it was 2.8% off on national season totals.

## Slide 5. Does it hold?

**On the slide**

- We hid one season at a time and predicted it from MODIS alone.
- 5.4%: average error on the national season total. 9.9% for a single region.
- The table:

| Conversion | Country, season | Region, season | Country, month | Region, month |
|---|---|---|---|---|
| One factor for everything | 6.7% | 14.4% | 15.1% | 27.4% |
| A factor per month and region | 7.3% | 11.7% | 14.4% | 26.2% |
| Count regression (used) | 5.4% | 9.9% | 12.8% | 23.5% |

- Every detection is kept. Dropping low-confidence ones was tested and predicted slightly worse (10.7% against 9.9% for a region's season).

**Visual:** the "Does it hold?" chart from the application (bars are what VIIRS counted, dots are the prediction from MODIS alone).

**Say:** This is the evidence. For each of the fourteen overlap seasons we fitted the conversion on the other thirteen and predicted the hidden one using only MODIS. The regression beats both simpler methods at every level, so it is the one in use. The same test decided the confidence question: filtering did not help, so nothing is thrown away.

## Slide 6. The application

**On the slide**

- Pick a place, read its fire history.
- Choose a region or district, type a latitude and longitude, or draw a shape on the map. Add a date range.
- The burning calendar: every season since 2000/01, month by month, in one colorblind-safe ramp.
- This month and the last 7 days against the same days of every earlier season.
- Download the hotspots as CSV, the calendar as CSV, or the whole page as PDF.

**Visual:** `app-calendar.png`, large. If there is room, a small crop of the tiles from `app-overview.png`.

**Say:** A person who has never seen it can pick their district, see when burning usually starts and peaks, see whether this November is normal, and leave with a file. Converted seasons are marked as estimates and carry a likely range, so nobody mistakes a conversion for an observation. If you have a live link, show it here instead of the screenshot.

## Slide 7. What it shows, and what it does not

**On the slide**

- What 26 years say about The Gambia:
  - Burning is usually under way by late December, peaks in February and fades by mid May. July to October holds 0.2% of the hotspots.
  - A normal season has about 5,280 hotspots. The quietest was 2014/15 with 2,822. The heaviest counted by VIIRS was 2023/24 with 7,460.
  - Mansakonko, the Lower River Region, burns most for its size: 78 hotspots per 100 km² in a normal season, against 57 in Basse and 30 in Kerewan. That matches what the Department of Forestry reports from the ground.
- Limits:
  - It covers The Gambia only.
  - Hotspots are detections of heat, not confirmed fires, and not burned area.
  - 2000/01 and 2001/02 rest on one satellite and are the least certain.
  - August to early October 2026 is missing between two data feeds.
- Data: NASA FIRMS (MODIS Collection 6.1, VIIRS S-NPP and NOAA-20 375 m). Boundaries: geoBoundaries, CC BY 4.0. Base map: OpenStreetMap contributors.

**Visual:** the map with regions shaded, or the season-by-season chart.

**Say:** The satellite record and the Forestry Department agree on where the burning is worst, which is a check from outside our own data. The limits are stated on the page as well as here. Next steps we would take: check the two earliest seasons against the MCD64A1 burned area product, add rainfall to explain early and late seasons, and write the plain-language briefing in Wolof and Mandinka.

## Research on The Gambia

### Verified (I opened the source)

- **Most forest land burns every year.** "Most of the country's forest lands are burnt annually." The same paper says "a significant number of forest fires result from field clearing" and lists hunting, honey collection, herding, fuelwood collection and smoking as the other traditional causes. It names the losses as "incalculable amounts of timber and fuelwood destroyed" and "low agricultural productivity resulting from soil degradation". Source: Almami Dampha with Kaniman Kamara and Clemens Beck, Forestry Department, Banjul, "Management of forest fires through the involvement of local communities: The Gambia", FAO, January 2001. <https://www.fao.org/4/AD348E/ad348e0a.htm>
- **The Lower River Region has the highest rate of bush fires.** Sulayman M.S. Gangne, head of the Information and Data Management Unit at the Department of Forestry, said statistics over the years show that "LRR records the highest rate of bush fires in The Gambia". The LRR governor, Seedy Lamin Bah, urged villages to build fire belts around forests in the dry season. Source: The Point, 14 May 2026. <https://thepoint.gm/africa/gambia/national-news/forestry-department-intensifies-fight-against-bush-burning-in-lrr>
- **The same was said in 2020.** The Minister for Environment, Lamin N. Dibba, told the National Assembly that "for the past years Lower River Region (LRR) recorded the highest bushfire outbreaks in the country", and that Kiang West forest park would be fenced against bush fire. Source: The Point, 13 July 2020. <https://thepoint.gm/africa/gambia/headlines/lrr-records-highest-number-of-bushfires-for-the-past-years-says-environment-minister>
- **Jamali Babou, December 2025.** A fire that started about 30 metres from the compound and spread on strong winds destroyed a family's home and its entire annual harvest (groundnut, maize, millet, rice) in Sami District, Central River Region. The cause is not stated. Source: The Point, 19 December 2025. <https://thepoint.gm/africa/gambia/national-news/inferno-destroys-family-home-harvest-in-jamali-babou>
- **Kiang Keneba, March 2021.** A fire destroyed dozens of cashew farms in the Lower River Region, including one with more than 1,300 cashew plants, and killed some domestic animals. The cause was not known. One farmer said the family normally earns over 100,000 dalasis a year after harvest. Source: The Point, 12 March 2021. <https://thepoint.gm/africa/gambia/headlines/fire-outbreak-destroys-dozens-of-cashew-farms-in-kiang>

### How our data lines up with it

- **Where:** Mansakonko (the Lower River Region) has the highest density in our record, 78 harmonized hotspots per 100 km² in a normal season. Then Basse 57, Kuntaur 55, Brikama 51, Janjanbureh 50, Kerewan 30. This agrees with both Forestry Department statements above. The region names in the application are the geoBoundaries names, so say "Mansakonko, the Lower River Region" when presenting.
- **When:** February holds 22% of all hotspots, March 19%, January 16%, April 15%, May 12%, December 8%, June 4%, November 4%. July to October together hold 0.2%. This fits the dry season that every source describes.
- **This month:** 69 hotspots from 1 to 14 November 2026 against a usual 38 by the same day, which the application rates as near normal.

### Reported by a search summary, not verified by me

Use these only after you have opened the source yourself.

- **More than 90% of bushfires are linked to human activity, and forest area is about 423,000 hectares.** Both are attributed to a 2024 CIFOR-ICRAF policy brief on bushfires in The Gambia, which is said to draw on burning alerts from 2010 to 2022 and government fire incident data from 2012 to 2022. The site refused my requests, so I could not read it. <https://cifor-icraf.org/publications/pdf/briefs/PB24001.pdf>
- **Population 2,422,712 in the 2024 census (preliminary).** Reported by The Point and attributed to the Gambia Bureau of Statistics. <https://thepoint.gm/africa/gambia/headlines/gambias-population-rises-to-2-4m-mandinkas-highest>
- **Land area about 10,120 km² (11,300 km² with water), forest cover about 22% in 2023.** From country profile sites, not from a Gambian source.
- **Community forestry began in 1991**, handing forest management to village committees, and beekeeping inside community forests is promoted as a reason to keep fire out. From FAO and World Rainforest Movement pages I did not open.
- **Upper Nuimi, North Bank Region:** over 200 hectares of cashew farms burned, about 40 farmers affected, losses put at 1.5 million dalasis. Voice Gambia, date unclear. <https://www.voicegambia.com/?p=38778>

### What I did not find

- No official yearly figure for hectares burned or number of fire incidents. The Department of Forestry statements give a ranking of regions, not counts.
- No recent measurement of what fires cost households nationally. The evidence is single incidents reported in the press.
