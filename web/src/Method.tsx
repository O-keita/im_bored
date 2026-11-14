import type { Method as MethodData } from './api'
import { count, monthShort, niceTicks, seasonLabel } from './format'
import { useTip, useWidth } from './hooks'

const HEIGHT = 240
const MARGIN = { top: 18, right: 12, bottom: 30, left: 44 }
const FIRE_MONTHS = [11, 12, 1, 2, 3, 4, 5, 6]

const LEVELS = ['national_season', 'region_season', 'national_month', 'region_month'] as const
const CONVERSIONS = [
  { key: 'single_factor', label: 'One factor for everything' },
  { key: 'month_and_region', label: 'A factor per month and region' },
  { key: 'count_model', label: 'Count regression (used)' },
] as const

const percent = (share: number) => `${Math.round(share * 100)}%`
const tenths = (share: number) => `${(share * 100).toFixed(1)}%`
const year = (isoDate: string) => isoDate.slice(0, 4)

/** How the two records were joined, and the test that shows it holds. */
export function Method({ method, firstYear }: { method: MethodData; firstYear: string }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const { tip, show, hide } = useTip()
  const { modis, terra } = method.eras
  const seasons = modis.held_out_seasons
  const keepAll = method.confidence_check.find((check) => check.rule === 'keep_all')
  const dropBoth = method.confidence_check.find((check) => check.rule === 'drop_both')

  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right)
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const ticks = niceTicks(Math.max(...seasons.flatMap((s) => [s.observed, s.predicted])))
  const top = ticks[ticks.length - 1]
  const y = (value: number) => MARGIN.top + plotHeight * (1 - value / top)
  const band = plotWidth / seasons.length
  const bar = Math.max(2, Math.min(24, band - 2))

  return (
    <div className="method">
      <div className="method-text">
        <p>
          Two kinds of sensor have watched these fires. MODIS has flown since {firstYear} and sees the
          ground in 1 km squares. VIIRS has flown since {year(method.viirs_start)} and sees it in 375 m squares, so it catches small fires that MODIS
          misses. Over the same ground and days, one MODIS detection stands for about <strong>{modis.overall_factor.toFixed(1)}</strong> VIIRS detections.
        </p>
        <p>
          Everything on this page is in VIIRS terms. From {year(method.viirs_start)} the counts are what VIIRS saw. Before that, each MODIS detection is
          scaled by a factor learnt from the {method.overlap_seasons[1] - method.overlap_seasons[0] + 1} seasons both sensors watched together. The factor
          changes with the month and the region, and it shrinks when a month is busy: where MODIS counts twice as many fires, VIIRS counts about{' '}
          {(2 ** modis.count_model.exponent).toFixed(1)} times as many, not twice. Averaged over those seasons, one MODIS detection stood for this
          many VIIRS detections:
        </p>
        <dl className="factors">
          {FIRE_MONTHS.map((month) => (
            <div key={month}>
              <dt>{monthShort(month)}</dt>
              <dd>×{modis.month_factor[String(month)].toFixed(1)}</dd>
            </div>
          ))}
        </dl>
        <p>
          Until {year(method.aqua_start)} only one MODIS satellite flew, so those detections are first scaled by ×{terra.terra_to_modis.toFixed(2)} to
          what two would have seen. The first two seasons are therefore the least certain. The VIIRS satellite used here stopped on {method.snpp_end};
          its twin, NOAA-20, carries the record on and counts within {percent(Math.abs(method.noaa20_factor - 1))} of it.
        </p>
      </div>

      <div className="method-proof">
        <h3>Does it hold? Each season predicted from MODIS alone</h3>
        <p className="sub">
          Each season was hidden in turn and predicted from the others. National season totals come out{' '}
          <strong>{tenths(modis.validation.national_season.count_model)}</strong> off on average, and a single region's{' '}
          <strong>{tenths(modis.validation.region_season.count_model)}</strong>.
        </p>
        <div ref={ref} className="chart">
          {width > 0 && (
            <svg width={width} height={HEIGHT} role="img" aria-label="Predicted against observed hotspots for each held-out season">
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
                const tipY = y(season.observed)
                const left = centre - bar / 2
                const radius = Math.min(4, bar / 2)
                return (
                  <g key={season.season}>
                    <path
                      className="column neutral"
                      d={`M${left},${y(0)} V${tipY + radius} Q${left},${tipY} ${left + radius},${tipY} H${left + bar - radius} Q${left + bar},${tipY} ${left + bar},${tipY + radius} V${y(0)} Z`}
                    />
                    <circle className="season-dot" cx={centre} cy={y(season.predicted)} r={5} />
                    {index % Math.ceil(60 / Math.max(band, 1)) === 0 && (
                      <text className="axis" x={centre} y={HEIGHT - 10} textAnchor="middle">
                        {seasonLabel(season.season)}
                      </text>
                    )}
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
                            <span className="tip-row">
                              <i className="key neutral" />
                              VIIRS counted {count(season.observed)}
                            </span>
                            <span className="tip-row">
                              <i className="key season-dot" />
                              Predicted from MODIS: {count(season.predicted)}
                            </span>
                            <span>{percent(Math.abs(season.predicted / season.observed - 1))} off</span>
                          </>,
                        )
                      }
                      onMouseLeave={hide}
                    />
                  </g>
                )
              })}
            </svg>
          )}
          <div className="legend">
            <span className="swatch-row">
              <i className="key neutral" />
              What VIIRS counted
            </span>
            <span className="swatch-row">
              <i className="key season-dot" />
              Predicted from MODIS alone
            </span>
          </div>
          {tip}
        </div>

        <table className="errors">
          <caption>Average error on hidden seasons, by conversion</caption>
          <thead>
            <tr>
              <th scope="col">Conversion</th>
              <th scope="col">Country, season</th>
              <th scope="col">Region, season</th>
              <th scope="col">Country, month</th>
              <th scope="col">Region, month</th>
            </tr>
          </thead>
          <tbody>
            {CONVERSIONS.map(({ key, label }) => (
              <tr key={key} className={key === 'count_model' ? 'used' : undefined}>
                <th scope="row">{label}</th>
                {LEVELS.map((level) => (
                  <td key={level}>{tenths(modis.validation[level][key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {keepAll && dropBoth && (
          <p className="sub">
            Every detection is kept, whatever its confidence. Dropping the low-confidence ones from both sensors was tried and predicted a region's
            season slightly worse: {tenths(dropBoth.region_season)} off against {tenths(keepAll.region_season)}. About{' '}
            {tenths(modis.missed_where_modis_saw_nothing)} of VIIRS detections fall in months where MODIS saw nothing in that region, and no conversion
            brings those back.
          </p>
        )}
      </div>
    </div>
  )
}
