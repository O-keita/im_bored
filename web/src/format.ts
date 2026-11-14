export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
] // prettier-ignore

export const monthName = (month: number) => MONTHS[month - 1]
export const monthShort = (month: number) => MONTHS[month - 1].slice(0, 3)

/** A fire season runs July to June, so season 2023 is written 2022/23. */
export const seasonLabel = (season: number) => `${season - 1}/${String(season).slice(2)}`

export const count = (value: number) => Math.round(value).toLocaleString('en')

/** Axis ticks: about `target` round steps from zero to just past `max`. */
export function niceTicks(max: number, target = 4): number[] {
  if (max <= 0) return [0, 1]
  const rough = max / target
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? 10 * magnitude
  const ticks = []
  for (let tick = 0; tick < max + step; tick += step) ticks.push(tick)
  return ticks
}

/**
 * One orange hue from light to dark, for magnitude on the light surface: darker means more.
 * Each step is 0.08 darker than the last in OKLCH lightness and the palest clears 2:1 against
 * the surface, so the order reads the same for colourblind viewers and in greyscale.
 */
export const RAMP = ['#e89e64', '#dc7c34', '#c65e0b', '#a94703', '#89340b', '#67260c', '#46180a']
export const EMPTY_CELL = '#eeede7'

const MONTH_DAY = { day: 'numeric', month: 'long', timeZone: 'UTC' } as const

/** Two ISO dates as a span, such as "8 to 14 February 2001". */
export function daySpan(from: string, to: string): string {
  const [start, end] = [new Date(from), new Date(to)]
  const sameMonth = start.getUTCMonth() === end.getUTCMonth() && start.getUTCFullYear() === end.getUTCFullYear()
  const first = sameMonth ? String(start.getUTCDate()) : start.toLocaleDateString('en-GB', MONTH_DAY)
  return `${first} to ${end.toLocaleDateString('en-GB', { ...MONTH_DAY, year: 'numeric' })}`
}

/** Lower bound of each ramp step. Steps widen with a square law so quiet months still separate. */
export function rampThresholds(max: number): number[] {
  return RAMP.map((_, i) => (i === 0 ? 0.5 : max * (i / RAMP.length) ** 2))
}

export function rampColor(value: number, thresholds: number[]): string {
  if (value < thresholds[0]) return EMPTY_CELL
  let step = 0
  while (step < thresholds.length - 1 && value >= thresholds[step + 1]) step++
  return RAMP[step]
}
