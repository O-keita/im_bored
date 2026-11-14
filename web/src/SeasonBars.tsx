import type { Summary } from './api'
import { count, niceTicks, seasonLabel } from './format'
import { useTip, useWidth } from './hooks'

const HEIGHT = 280
const MARGIN = { top: 18, right: 12, bottom: 30, left: 44 }

/** One column per fire season. Converted seasons are paler and carry their range. */
export function SeasonBars({ summary }: { summary: Summary }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const { tip, show, hide } = useTip()
  const seasons = summary.seasons
  const median = summary.typical.season_total

  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right)
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const ticks = niceTicks(Math.max(median, ...seasons.map((s) => s.high)))
  const top = ticks[ticks.length - 1]
  const y = (value: number) => MARGIN.top + plotHeight * (1 - value / top)
  const band = seasons.length ? plotWidth / seasons.length : 0
  const bar = Math.max(2, Math.min(24, band - 2))
  const labelEvery = Math.ceil(60 / Math.max(band, 1))
  const heaviest = seasons.reduce((best, s) => (s.complete && s.total > (best?.total ?? -1) ? s : best), seasons[0])

  return (
    <div ref={ref} className="chart">
      {width > 0 && (
        <svg width={width} height={HEIGHT} role="img" aria-label="Harmonized hotspots in each fire season">
          {ticks.map((tick) => (
            <g key={tick}>
              <line className="grid" x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} />
              <text className="axis" x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
                {count(tick)}
              </text>
            </g>
          ))}

          {seasons.map((season, index) => {
            const centre = MARGIN.left + band * (index + 0.5)
            const tipY = y(season.total)
            const radius = Math.min(4, bar / 2, y(0) - tipY)
            const left = centre - bar / 2
            const converted = season.kind !== 'observed'
            return (
              <g key={season.season}>
                {/* Rounded at the data end, square on the baseline. */}
                <path
                  className={`column${converted ? ' converted' : ''}${season.complete ? '' : ' partial'}`}
                  d={`M${left},${y(0)} V${tipY + radius} Q${left},${tipY} ${left + radius},${tipY} H${left + bar - radius} Q${left + bar},${tipY} ${left + bar},${tipY + radius} V${y(0)} Z`}
                />
                {converted && <line className="range" x1={centre} x2={centre} y1={y(season.high)} y2={y(season.low)} />}
                {(season === heaviest || !season.complete) && (
                  <text className="value" x={centre} y={Math.min(tipY, y(season.high)) - 6} textAnchor="middle">
                    {count(season.total)}
                  </text>
                )}
                {index % labelEvery === 0 && (
                  <text className="axis" x={centre} y={HEIGHT - 10} textAnchor="middle">
                    {seasonLabel(season.season)}
                  </text>
                )}
                {/* The hit target is the whole band, not just the column. */}
                <rect
                  x={centre - band / 2}
                  y={MARGIN.top}
                  width={band}
                  height={plotHeight}
                  fill="transparent"
                  onMouseMove={(event) =>
                    show(
                      event,
                      <>
                        <strong>{seasonLabel(season.season)}</strong>
                        {count(season.total)} hotspots{season.complete ? '' : ' so far'}
                        {converted && (
                          <span>
                            Converted from MODIS. Likely between {count(season.low)} and {count(season.high)}.
                          </span>
                        )}
                        {!converted && <span>Counted by VIIRS.</span>}
                      </>,
                    )
                  }
                  onMouseLeave={hide}
                />
              </g>
            )
          })}

          {median > 0 && (
            <g>
              <line className="reference" x1={MARGIN.left} x2={width - MARGIN.right} y1={y(median)} y2={y(median)} />
              <text className="reference-label" x={width - MARGIN.right} y={y(median) - 6} textAnchor="end">
                normal season, {count(median)}
              </text>
            </g>
          )}
        </svg>
      )}
      <div className="legend">
        <span className="swatch-row">
          <i className="key observed" />
          Counted by VIIRS
        </span>
        <span className="swatch-row">
          <i className="key converted" />
          Converted from MODIS
        </span>
        <span className="swatch-row">
          <i className="key range" />
          Likely range
        </span>
      </div>
      {tip}
    </div>
  )
}
