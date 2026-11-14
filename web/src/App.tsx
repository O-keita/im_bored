import { useEffect, useMemo, useState } from 'react'
import {
  downloadCsv,
  getAreas,
  getBoundaries,
  getHealth,
  getHotspots,
  getMethod,
  getRaw,
  getSummary,
  type Area,
  type Health,
  type Hotspots,
  type Method as MethodData,
  type RawCalendar,
  type Query,
  type RegionInfo,
  type Summary,
} from './api'
import { Calendar } from './Calendar'
import { count, daySpan, monthName, seasonLabel } from './format'
import { MapView, type Vertex } from './MapView'
import { Method } from './Method'
import { Records } from './Records'
import { SeasonBars } from './SeasonBars'
import { SeasonCurve } from './SeasonCurve'

type Mode = 'place' | 'circle' | 'polygon'

const MODES: { value: Mode; label: string }[] = [
  { value: 'place', label: 'Region or district' },
  { value: 'circle', label: 'Around a point' },
  { value: 'polygon', label: 'Draw a shape' },
]

const STATUS_ICON: Record<string, string> = {
  'well above normal': '▲▲',
  'above normal': '▲',
  'near normal': '●',
  'below normal': '▼',
  'well below normal': '▼▼',
}

function Status({ status }: { status: string }) {
  return (
    <span className="status" data-level={status.replaceAll(' ', '-')}>
      <span aria-hidden="true">{STATUS_ICON[status]}</span> {status}
    </span>
  )
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [regions, setRegions] = useState<RegionInfo[]>([])
  const [regionShapes, setRegionShapes] = useState<GeoJSON.FeatureCollection | null>(null)
  const [districtShapes, setDistrictShapes] = useState<GeoJSON.FeatureCollection | null>(null)
  const [method, setMethod] = useState<MethodData | null>(null)

  const [mode, setMode] = useState<Mode>('place')
  const [region, setRegion] = useState('')
  const [district, setDistrict] = useState('')
  const [centre, setCentre] = useState({ latitude: 13.45, longitude: -15.4 })
  const [radiusKm, setRadiusKm] = useState(15)
  const [shape, setShape] = useState<Vertex[]>([])
  const [drawing, setDrawing] = useState(false)
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [streets, setStreets] = useState(false)

  const [summary, setSummary] = useState<Summary | null>(null)
  const [hotspots, setHotspots] = useState<Hotspots | null>(null)
  const [raw, setRaw] = useState<RawCalendar | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getHealth(), getAreas(), getBoundaries('adm1'), getBoundaries('adm2'), getMethod()])
      .then(([healthBody, areas, adm1, adm2, methodBody]) => {
        setHealth(healthBody)
        setRegions(areas.regions)
        setRegionShapes(adm1)
        setDistrictShapes(adm2)
        setMethod(methodBody)
      })
      .catch(() => setError('The data service is not reachable. Start it with: uv run uvicorn firecal.api:app --port 8010'))
  }, [])

  const area = useMemo<Area>(() => {
    if (mode === 'circle' && radiusKm > 0) return { type: 'circle', ...centre, radius_km: radiusKm }
    if (mode === 'polygon' && !drawing && shape.length >= 3) {
      return { type: 'polygon', coordinates: shape.map(([latitude, longitude]) => [longitude, latitude]) }
    }
    if (mode === 'place' && district) return { type: 'district', name: district }
    if (mode === 'place' && region) return { type: 'region', name: region }
    return { type: 'country' }
  }, [mode, region, district, centre, radiusKm, shape, drawing])

  const query = useMemo<Query>(() => ({ area, start: start || null, end: end || null }), [area, start, end])

  useEffect(() => {
    const controller = new AbortController()
    // Wait briefly so typing a radius or a date does not fire a request per keystroke.
    const timer = setTimeout(() => {
      setLoading(true)
      Promise.all([getSummary(query, controller.signal), getHotspots(query, controller.signal), getRaw(query.area, controller.signal)])
        .then(([summaryBody, hotspotsBody, rawBody]) => {
          setSummary(summaryBody)
          setHotspots(hotspotsBody)
          setRaw(rawBody)
          setError(null)
          setLoading(false)
        })
        .catch((reason: Error) => {
          if (reason.name === 'AbortError') return
          setError(reason.message)
          setLoading(false)
        })
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const title =
    area.type === 'district' || area.type === 'region'
      ? area.name
      : area.type === 'circle'
        ? `${area.radius_km} km around a point`
        : area.type === 'polygon'
          ? 'Your drawn area'
          : 'The Gambia'

  const showCountry = () => {
    setMode('place')
    setRegion('')
    setDistrict('')
  }
  const selectRegion = (name: string) => {
    setMode('place')
    setRegion(name)
    setDistrict('')
  }
  const changeMode = (next: Mode) => {
    setMode(next)
    setDrawing(next === 'polygon' && shape.length < 3)
  }
  const redraw = () => {
    setShape([])
    setDrawing(true)
  }

  const current = summary?.current
  const typical = summary?.typical
  const hasHistory = (typical?.season_total ?? 0) > 0
  const week = summary?.last_week
  // With no hotspot in the whole record, a drawn area is either outside the border or has never burned.
  const outsideCoverage = (area.type === 'circle' || area.type === 'polygon') && summary !== null && summary.seasons.every((s) => s.total === 0)

  return (
    <div className="page">
      <header className="masthead">
        <span className="wordmark">Gambia Fire Calendar</span>
        <span className="meta">
          {health ? `Satellite record, ${health.first_date.slice(0, 4)} to ${health.last_date}` : 'Loading the record'} · NASA FIRMS
        </span>
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <section className="hero">
        <div className="intro">
          <nav className="crumbs" aria-label="Selected area">
            <button type="button" onClick={showCountry}>
              The Gambia
            </button>
            {mode === 'place' && region && (
              <button type="button" onClick={() => setDistrict('')}>
                {region}
              </button>
            )}
            {mode === 'place' && district && <span>{district}</span>}
          </nav>
          <h1>{title}</h1>

          {summary && current && typical && (
            <p className="briefing">
              {hasHistory ? (
                <>
                  Burning here is usually under way by {typical.start}, peaks in {monthName(typical.peak_month)} and fades by {typical.end}. So far
                  this {monthName(current.month)} it is <strong>{current.month_status}</strong>: {count(current.month_to_date)} hotspots against a
                  usual {count(current.month_median)} by day {current.through_day}.
                </>
              ) : (
                <>Satellites have detected almost no burning in this area since {health?.first_date.slice(0, 4)}.</>
              )}
            </p>
          )}

          <div className="controls">
            <div className="segmented" role="radiogroup" aria-label="How to choose an area">
              {MODES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={mode === option.value}
                  onClick={() => changeMode(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {mode === 'place' && (
              <>
                <div className="pair">
                  <label>
                    Region
                    <select
                      value={region}
                      onChange={(event) => {
                        setRegion(event.target.value)
                        setDistrict('')
                      }}
                    >
                      <option value="">All regions</option>
                      {regions.map((r) => (
                        <option key={r.name}>{r.name}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    District
                    <select value={district} disabled={!region} onChange={(event) => setDistrict(event.target.value)}>
                      <option value="">All districts</option>
                      {regions
                        .find((r) => r.name === region)
                        ?.districts.map((d) => (
                          <option key={d.name}>{d.name}</option>
                        ))}
                    </select>
                  </label>
                </div>
                <p className="hint">Or click a region on the map, then a district inside it.</p>
              </>
            )}

            {mode === 'circle' && (
              <>
                <div className="triple">
                  <label>
                    Latitude
                    <input
                      type="number"
                      step="0.01"
                      value={centre.latitude}
                      onChange={(e) => setCentre({ ...centre, latitude: e.target.valueAsNumber })}
                    />
                  </label>
                  <label>
                    Longitude
                    <input
                      type="number"
                      step="0.01"
                      value={centre.longitude}
                      onChange={(e) => setCentre({ ...centre, longitude: e.target.valueAsNumber })}
                    />
                  </label>
                  <label>
                    Radius, km
                    <input type="number" min="1" max="500" value={radiusKm} onChange={(e) => setRadiusKm(e.target.valueAsNumber)} />
                  </label>
                </div>
                <p className="hint">Click the map to move the centre.</p>
              </>
            )}

            {mode === 'polygon' && (
              <>
                <div className="row">
                  {drawing ? (
                    <button type="button" className="quiet" disabled={shape.length < 3} onClick={() => setDrawing(false)}>
                      Finish shape
                    </button>
                  ) : (
                    <button type="button" className="quiet" onClick={redraw}>
                      Draw again
                    </button>
                  )}
                  {drawing && shape.length > 0 && (
                    <button type="button" className="quiet" onClick={() => setShape(shape.slice(0, -1))}>
                      Undo last point
                    </button>
                  )}
                </div>
                <p className="hint">
                  {drawing
                    ? shape.length < 3
                      ? `Click the map to place corners. ${3 - shape.length} more needed.`
                      : 'Keep adding corners, or finish the shape.'
                    : 'Showing the area inside your shape.'}
                </p>
              </>
            )}

            <div className="pair">
              <label>
                From
                <input
                  type="date"
                  value={start}
                  min={health?.first_date}
                  max={end || health?.last_date}
                  onChange={(e) => setStart(e.target.value)}
                />
              </label>
              <label>
                To
                <input
                  type="date"
                  value={end}
                  min={start || health?.first_date}
                  max={health?.last_date}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </label>
            </div>

            <div className="downloads">
              <button
                type="button"
                className="primary"
                disabled={!hotspots?.detections}
                onClick={() => downloadCsv(query, 'hotspots').catch((e) => setError(e.message))}
              >
                Download hotspots CSV
              </button>
              <button
                type="button"
                className="quiet"
                disabled={!hotspots?.detections}
                onClick={() => downloadCsv(query, 'calendar').catch((e) => setError(e.message))}
              >
                Download calendar CSV
              </button>
              <button type="button" className="quiet" onClick={() => window.print()}>
                Save page as PDF
              </button>
            </div>
            {hotspots && (
              <p className="hint">
                {hotspots.detections > 0
                  ? `${count(hotspots.detections)} detections from all sensors. The calendar file has the harmonized count for every month, with how far it sits from the usual.`
                  : outsideCoverage
                    ? 'Nothing was detected here. The record covers The Gambia only, so an area outside its border is always empty.'
                    : 'Nothing was detected here in these dates.'}
              </p>
            )}
          </div>
        </div>

        <div className="map-frame" aria-busy={loading}>
          <MapView
            area={area}
            regions={regions}
            regionShapes={regionShapes}
            districtShapes={districtShapes}
            points={hotspots?.points ?? []}
            drawing={mode === 'polygon' && drawing ? shape : null}
            pickingCentre={mode === 'circle'}
            streets={streets}
            onSelectRegion={selectRegion}
            onSelectDistrict={setDistrict}
            onPickCentre={(latitude, longitude) =>
              setCentre({ latitude: Number(latitude.toFixed(4)), longitude: Number(longitude.toFixed(4)) })
            }
            onAddVertex={(vertex) => setShape((vertices) => [...vertices, vertex])}
          />
          <div className="map-foot">
            <span className="swatch-row">
              <i className="dot" />
              {hotspots
                ? hotspots.shown < hotspots.total
                  ? `Each dot is a detected fire. Showing ${count(hotspots.shown)} of ${count(hotspots.total)}, spread evenly through time.`
                  : `Each dot is a detected fire. ${count(hotspots.total)} shown.`
                : 'Each dot is a detected fire.'}
            </span>
            <label className="toggle">
              <input type="checkbox" checked={streets} onChange={(event) => setStreets(event.target.checked)} />
              Roads and towns
            </label>
          </div>
        </div>
      </section>

      {summary && current && typical && (
        <>
          <section className="tiles" aria-busy={loading}>
            <article>
              <h2>{monthName(current.month)} so far</h2>
              <p className="figure">{count(current.month_to_date)}</p>
              <p className="note">
                <Status status={current.month_status} />
                <br />
                usually {count(current.month_median)} by day {current.through_day}
              </p>
            </article>
            {week && (
              <article>
                <h2>Last 7 days</h2>
                <p className="figure">{count(week.total)}</p>
                <p className="note">
                  <Status status={week.status} />
                  <br />
                  usually {count(week.median)} in these days.
                  {week.record_from && week.record_to && week.record_total > 0 && (
                    <>
                      {' '}
                      Busiest week on record: {count(week.record_total)}, {daySpan(week.record_from, week.record_to)}
                      {method && week.record_to < method.viirs_start ? ' (converted from MODIS)' : ''}.
                    </>
                  )}
                </p>
              </article>
            )}
            <article>
              <h2>Season so far, since July</h2>
              <p className="figure">{count(current.season_to_date)}</p>
              <p className="note">
                <Status status={current.season_status} />
                <br />
                usually {count(current.season_to_date_median)} by this date
              </p>
            </article>
            <article>
              <h2>Usual peak</h2>
              <p className="figure">{hasHistory ? monthName(typical.peak_month) : 'None'}</p>
              <p className="note">
                {hasHistory
                  ? `Under way by ${typical.start}, fading by ${typical.end}. A normal season has ${count(typical.season_total)} hotspots.`
                  : 'Too little burning to time a season.'}
              </p>
            </article>
            <article>
              <h2>Heaviest season</h2>
              <p className="figure">{typical.worst_season ? seasonLabel(typical.worst_season) : 'None'}</p>
              <p className="note">
                {count(typical.worst_total)} hotspots.
                {typical.quietest_season && ` Quietest: ${seasonLabel(typical.quietest_season)}, with ${count(typical.quietest_total)}.`}
              </p>
            </article>
          </section>

          <section className="block" aria-busy={loading}>
            <header>
              <h2>The burning calendar</h2>
              <p>
                Every fire season since {seasonLabel(summary.calendar.seasons[0] ?? summary.current_season)}, month by month. A season runs July
                to June. Darker means more fires. Seasons marked <abbr title="Converted from MODIS">est.</abbr> are converted from the older
                sensor.
              </p>
            </header>
            <Calendar summary={summary} />
          </section>

          <div className="split">
            <section className="block" aria-busy={loading}>
              <header>
                <h2>Season by season</h2>
                <p>Total hotspots in each fire season, in one unit across the whole record.</p>
              </header>
              <SeasonBars summary={summary} />
            </section>
            <section className="block" aria-busy={loading}>
              <header>
                <h2>One season against a normal one</h2>
                <p>Hotspots by month. The band is where the middle half of past seasons fell.</p>
              </header>
              <SeasonCurve summary={summary} />
            </section>
          </div>
        </>
      )}

      {method && health && (
        <section className="block">
          <header>
            <h2>How 26 years became one record</h2>
            <p>
              The old and new satellites count fires differently. Below are their separate counts for {title === 'The Gambia' ? 'the country' : 'this area'}, the
              single record made from them, and the test of whether the conversion works.
            </p>
          </header>
          {summary && raw && <Records summary={summary} raw={raw} />}
          <Method method={method} firstYear={health.first_date.slice(0, 4)} />
        </section>
      )}

      <footer className="credits">
        <p>
          This tool covers The Gambia: every area you pick or draw is read from the record inside its border. Hotspots are satellite
          detections of heat, not confirmed fires, and small or short fires can be missed. The current year is
          provisional, and August to early October {health?.last_date.slice(0, 4)} is missing between two data feeds; almost nothing burns in
          those months.
        </p>
        <p>
          Active fire data: NASA FIRMS (MODIS Collection 6.1, VIIRS S-NPP and NOAA-20). Boundaries: geoBoundaries, CC BY 4.0. Road map:
          OpenStreetMap contributors. Typefaces: Instrument Serif and Inter, SIL Open Font License. Built for the NASA Space Apps Challenge 2026.
        </p>
      </footer>
    </div>
  )
}
