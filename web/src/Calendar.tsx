import { useState } from 'react'
import type { Summary } from './api'
import { count, EMPTY_CELL, monthName, monthShort, RAMP, rampColor, rampThresholds, seasonLabel } from './format'
import { useTip } from './hooks'

const KIND_NOTE = {
  observed: 'Counted by VIIRS',
  converted: 'Converted from MODIS',
  mixed: 'Part converted from MODIS, part counted by VIIRS',
}

export function Calendar({ summary }: { summary: Summary }) {
  const [asTable, setAsTable] = useState(false)
  const { tip, show, hide } = useTip()
  const { months, calendar, seasons } = summary

  // Newest season first: the season in progress is what most people come for.
  const rows = seasons.map((season, index) => ({ season, counts: calendar.counts[index] })).reverse()
  const max = Math.max(1, ...calendar.counts.flat())
  const thresholds = rampThresholds(max)
  const maxTotal = Math.max(1, ...seasons.map((s) => s.total))

  return (
    <div className="calendar">
      <div className="chart-actions">
        <button type="button" className="quiet" aria-pressed={asTable} onClick={() => setAsTable(!asTable)}>
          {asTable ? 'Show as heatmap' : 'Show the numbers'}
        </button>
      </div>

      <div className="calendar-scroll">
        <table className={asTable ? 'numbers' : 'heat'}>
          <thead>
            <tr>
              <th scope="col" className="row-head">
                Season
              </th>
              {months.map((month) => (
                <th key={month} scope="col">
                  {monthShort(month)}
                </th>
              ))}
              <th scope="col" className="total-head">
                Season total
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ season, counts }) => (
              <tr key={season.season}>
                <th scope="row" className="row-head">
                  {seasonLabel(season.season)}
                  {season.kind !== 'observed' && <abbr title={KIND_NOTE[season.kind]}>est.</abbr>}
                  {!season.complete && <abbr title="This season is still in progress">so far</abbr>}
                </th>
                {counts.map((value, column) => {
                  const month = months[column]
                  const detail = (
                    <>
                      <strong>
                        {monthName(month)} {month >= 7 ? season.season - 1 : season.season}
                      </strong>
                      {count(value)} hotspots
                      <span>{KIND_NOTE[season.kind]}</span>
                    </>
                  )
                  return asTable ? (
                    <td key={month}>{value >= 0.5 ? count(value) : ''}</td>
                  ) : (
                    <td key={month} onMouseMove={(event) => show(event, detail)} onMouseLeave={hide}>
                      <i style={{ background: rampColor(value, thresholds) }} />
                    </td>
                  )
                })}
                <td className="total">
                  <span className="bar" style={{ width: `${(season.total / maxTotal) * 100}%` }} data-kind={season.kind} />
                  <span>{count(season.total)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!asTable && (
        <div className="legend" aria-label="Colour scale: hotspots in a month">
          <span>Hotspots in a month</span>
          <span className="swatch-row">
            <i style={{ background: EMPTY_CELL }} />0
          </span>
          {RAMP.map((color, step) => (
            <span key={color} className="swatch-row">
              <i style={{ background: color }} />
              {step === 0 ? '1' : count(thresholds[step])}
              {step === RAMP.length - 1 && '+'}
            </span>
          ))}
        </div>
      )}
      {tip}
    </div>
  )
}
