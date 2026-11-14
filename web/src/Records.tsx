import type { ReactNode } from 'react'
import type { RawCalendar, Summary } from './api'
import { count, niceTicks, seasonLabel } from './format'
import { useTip, useWidth } from './hooks'

const HEIGHT = 250
const MARGIN = { top: 18, right: 12, bottom: 30, left: 44 }

const SENSORS = [
  { id: 'MODIS', label: 'MODIS, 1 km', key: 'modis' },
  { id: 'VIIRS_SNPP', label: 'VIIRS S-NPP, 375 m', key: 'snpp' },
  { id: 'VIIRS_NOAA20', label: 'VIIRS NOAA-20, 375 m', key: 'noaa20' },
] as const

interface Series {
  key: string
  label: string
  /** One value per season on the axis, null where this record has nothing to show. */
  values: (number | null)[]
}

/** Draws a line through each unbroken run of values. */
const runs = (values: (number | null)[], x: (i: number) => number, y: (v: number) => number) =>
  values.map((v, i) => (v === null ? '' : `${i > 0 && values[i - 1] !== null ? 'L' : 'M'}${x(i)},${y(v)}`)).join(' ')

function Panel({
  title,
  seasons,
  series,
  top,
  ticks,
  band,
  divider,
  describe,
}: {
  title: string
  seasons: number[]
  series: Series[]
  top: number
  ticks: number[]
  /** Likely range, drawn only where low and high differ. */
  band?: { low: number[]; high: number[] }
  /** Index of the first season counted by VIIRS, to mark the handover. */
  divider?: number
  describe: (index: number) => ReactNode
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const { tip, show, hide } = useTip()
  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right)
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const step = seasons.length ? plotWidth / seasons.length : 0
  const x = (index: number) => MARGIN.left + step * (index + 0.5)
  const y = (value: number) => MARGIN.top + plotHeight * (1 - value / top)
  const labelEvery = Math.ceil(60 / Math.max(step, 1))
  const ranged = band ? seasons.map((_, i) => i).filter((i) => band.high[i] > band.low[i]) : []

  return (
    <div className="records-panel">
      <h3>{title}</h3>
      <div ref={ref} className="chart">
        {width > 0 && (
          <svg width={width} height={HEIGHT} role="img" aria-label={title}>
            {ticks.map((tick) => (
              <g key={tick}>
                <line className="grid" x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} />
                <text className="axis" x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
                  {count(tick)}
                </text>
              </g>
            ))}
            {seasons.map(
              (season, index) =>
                index % labelEvery === 0 && (
                  <text key={season} className="axis" x={x(index)} y={HEIGHT - 10} textAnchor="middle">
                    {seasonLabel(season)}
                  </text>
                ),
            )}
            {divider !== undefined && divider > 0 && (
              <g>
                <line className="handover" x1={x(divider) - step / 2} x2={x(divider) - step / 2} y1={MARGIN.top} y2={y(0)} />
                <text className="reference-label" x={x(divider) - step / 2 - 6} y={MARGIN.top + 4} textAnchor="end">
                  converted
                </text>
                <text className="reference-label" x={x(divider) - step / 2 + 6} y={MARGIN.top + 4}>
                  counted by VIIRS
                </text>
              </g>
            )}
            {band && ranged.length > 1 && (
              <path
                className="record-band"
                d={`${ranged.map((i, n) => `${n ? 'L' : 'M'}${x(i)},${y(band.high[i])}`).join(' ')} ${[...ranged]
                  .reverse()
                  .map((i) => `L${x(i)},${y(band.low[i])}`)
                  .join(' ')} Z`}
              />
            )}
            {series.map((line) => (
              <g key={line.key}>
                <path className={`record-line ${line.key}`} d={runs(line.values, x, y)} />
                {/* A season with no neighbours would otherwise draw nothing. */}
                {line.values.map(
                  (value, index) =>
                    value !== null &&
                    line.values[index - 1] == null &&
                    line.values[index + 1] == null && <circle key={index} className={`record-point ${line.key}`} cx={x(index)} cy={y(value)} r={3} />,
                )}
              </g>
            ))}
            {seasons.map((season, index) => (
              <rect
                key={season}
                x={x(index) - step / 2}
                y={MARGIN.top}
                width={step}
                height={plotHeight}
                fill="transparent"
                onMouseMove={(event) =>
                  show(
                    event,
                    <>
                      <strong>{seasonLabel(season)}</strong>
                      {describe(index)}
                    </>,
                  )
                }
                onMouseLeave={hide}
              />
            ))}
          </svg>
        )}
        <div className="legend">
          {series.map((line) => (
            <span key={line.key} className="swatch-row">
              <i className={`key record ${line.key}`} />
              {line.label}
            </span>
          ))}
          {band && ranged.length > 1 && (
            <span className="swatch-row">
              <i className="key record-band" />
              Likely range
            </span>
          )}
        </div>
        {tip}
      </div>
    </div>
  )
}

/** The raw record of each satellite beside the single harmonized record, on one scale. */
export function Records({ summary, raw }: { summary: Summary; raw: RawCalendar }) {
  const shown = summary.seasons.filter((s) => s.complete)
  const seasons = shown.map((s) => s.season)

  const rawSeries: Series[] = SENSORS.filter((sensor) => raw.sensors[sensor.id]).map((sensor) => {
    const record = raw.sensors[sensor.id]
    const totals = new Map(record.seasons.map((season, i) => [season, record.counts[i].reduce((a, b) => a + b, 0)]))
    return {
      key: sensor.key,
      label: sensor.label,
      // A sensor's first season only counts if it was flying before burning began in November.
      values: seasons.map((season) =>
        season >= record.seasons[0] && record.first_date <= `${season - 1}-11-30` && season <= record.seasons[record.seasons.length - 1]
          ? (totals.get(season) ?? 0)
          : null,
      ),
    }
  })
  const harmonized: Series = { key: 'harmonized', label: 'VIIRS-equivalent hotspots', values: shown.map((s) => s.total) }
  const band = { low: shown.map((s) => s.low), high: shown.map((s) => s.high) }
  const firstObserved = shown.findIndex((s) => s.kind !== 'converted')

  const ticks = niceTicks(Math.max(1, ...band.high, ...rawSeries.flatMap((s) => s.values.map((v) => v ?? 0))))
  const top = ticks[ticks.length - 1]

  if (seasons.length < 2) return null
  return (
    <div className="records">
      <Panel
        title="What each satellite counted"
        seasons={seasons}
        series={rawSeries}
        top={top}
        ticks={ticks}
        describe={(index) =>
          rawSeries.map((line) => (
            <span key={line.key} className="tip-row">
              <i className={`key record ${line.key}`} />
              {line.label.split(',')[0]}: {line.values[index] === null ? 'not flying' : count(line.values[index] ?? 0)}
            </span>
          ))
        }
      />
      <Panel
        title="The same seasons as one record"
        seasons={seasons}
        series={[harmonized]}
        top={top}
        ticks={ticks}
        band={band}
        divider={firstObserved > 0 ? firstObserved : undefined}
        describe={(index) => (
          <>
            <span className="tip-row">
              <i className="key record harmonized" />
              {count(shown[index].total)} hotspots
            </span>
            {shown[index].kind === 'observed' ? (
              <span>Counted by VIIRS.</span>
            ) : (
              <span>
                Converted from MODIS. Likely between {count(shown[index].low)} and {count(shown[index].high)}.
              </span>
            )}
          </>
        )}
      />
    </div>
  )
}
