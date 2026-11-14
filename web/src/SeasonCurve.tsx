import { useState } from 'react'
import type { Summary } from './api'
import { count, monthName, monthShort, niceTicks, seasonLabel } from './format'
import { useTip, useWidth } from './hooks'

const HEIGHT = 280
const MARGIN = { top: 18, right: 16, bottom: 30, left: 44 }

/** The normal shape of a season (median and middle half) with one chosen season drawn over it. */
export function SeasonCurve({ summary }: { summary: Summary }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const { tip, show, hide } = useTip()
  const [picked, setPicked] = useState<number | null>(null)
  const { months, normal, calendar, current_season } = summary

  const season = picked !== null && calendar.seasons.includes(picked) ? picked : (calendar.seasons.at(-1) ?? current_season)
  const values = calendar.counts[calendar.seasons.indexOf(season)] ?? []
  // The season in progress has no data past the current month, so its line stops there.
  const lastMonth = season === current_season ? months.indexOf(summary.current.month) : months.length - 1
  const drawn = values.slice(0, lastMonth + 1)

  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right)
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const ticks = niceTicks(Math.max(...normal.high, ...drawn, 1))
  const top = ticks[ticks.length - 1]
  const step = plotWidth / months.length
  const x = (index: number) => MARGIN.left + step * (index + 0.5)
  const y = (value: number) => MARGIN.top + plotHeight * (1 - value / top)
  const line = (series: number[]) => series.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ')
  // Along the upper quartile, then back along the lower one.
  const lowerEdge = normal.low.map((v, i) => `L${x(i)},${y(v)}`).reverse()
  const band = `${line(normal.high)} ${lowerEdge.join(' ')} Z`

  return (
    <div ref={ref} className="chart">
      <div className="chart-actions">
        <label className="inline">
          Compare
          <select value={season} onChange={(event) => setPicked(Number(event.target.value))}>
            {[...calendar.seasons].reverse().map((s) => (
              <option key={s} value={s}>
                {seasonLabel(s)}
                {s === current_season ? ' (so far)' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>
      {width > 0 && (
        <svg width={width} height={HEIGHT} role="img" aria-label={`Hotspots by month in ${seasonLabel(season)} against a normal season`}>
          {ticks.map((tick) => (
            <g key={tick}>
              <line className="grid" x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} />
              <text className="axis" x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
                {count(tick)}
              </text>
            </g>
          ))}
          {months.map((month, index) => (
            <text key={month} className="axis" x={x(index)} y={HEIGHT - 10} textAnchor="middle">
              {monthShort(month)}
            </text>
          ))}

          <path className="normal-band" d={band} />
          <path className="normal-line" d={line(normal.median)} />
          {drawn.length > 0 && <path className="season-line" d={line(drawn)} />}
          {drawn.length > 0 && <circle className="season-dot" cx={x(drawn.length - 1)} cy={y(drawn[drawn.length - 1])} r={5} />}

          {months.map((month, index) => (
            <rect
              key={month}
              x={x(index) - step / 2}
              y={MARGIN.top}
              width={step}
              height={plotHeight}
              fill="transparent"
              onMouseMove={(event) =>
                show(
                  event,
                  <>
                    <strong>{monthName(month)}</strong>
                    {index <= lastMonth && (
                      <span className="tip-row">
                        <i className="key season" />
                        {seasonLabel(season)}: {count(values[index])}
                      </span>
                    )}
                    <span className="tip-row">
                      <i className="key normal" />
                      Normal: {count(normal.median[index])}
                    </span>
                    <span>
                      Middle half of seasons: {count(normal.low[index])} to {count(normal.high[index])}
                    </span>
                  </>,
                )
              }
              onMouseLeave={hide}
            />
          ))}
        </svg>
      )}
      <div className="legend">
        <span className="swatch-row">
          <i className="key season" />
          {seasonLabel(season)}
          {season === current_season ? ' so far' : ''}
        </span>
        <span className="swatch-row">
          <i className="key normal" />
          Normal season (median)
        </span>
        <span className="swatch-row">
          <i className="key band" />
          Middle half of seasons
        </span>
      </div>
      {tip}
    </div>
  )
}
