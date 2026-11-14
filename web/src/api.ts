export type Area =
  | { type: 'country' }
  | { type: 'region'; name: string }
  | { type: 'district'; name: string }
  | { type: 'circle'; latitude: number; longitude: number; radius_km: number }
  /** Ring of [longitude, latitude] pairs. */
  | { type: 'polygon'; coordinates: [number, number][] }

export interface Query {
  area: Area
  start: string | null
  end: string | null
}

export interface AreaInfo {
  name: string
  area_km2: number
  /** [latitude, longitude] of a point inside the area, for its label. */
  label: [number, number]
  /** Median harmonized hotspots per complete season. */
  median_season: number
  per_100km2: number
}

export interface RegionInfo extends AreaInfo {
  districts: AreaInfo[]
}

export type SeasonKind = 'observed' | 'converted' | 'mixed'

export interface SeasonTotal {
  season: number
  total: number
  low: number
  high: number
  kind: SeasonKind
  complete: boolean
}

export interface Summary {
  as_of: string
  /** Month numbers in fire-season order, July first. Every 12-long array below follows it. */
  months: number[]
  current_season: number
  calendar: { seasons: number[]; counts: number[][] }
  seasons: SeasonTotal[]
  normal: { median: number[]; low: number[]; high: number[] }
  typical: {
    seasons_used: number
    season_total: number
    peak_month: number
    start: string | null
    end: string | null
    worst_season: number | null
    worst_total: number
    quietest_season: number | null
    quietest_total: number
  }
  current: {
    month: number
    through_day: number
    month_to_date: number
    month_median: number
    month_percentile: number
    month_status: string
    season_to_date: number
    season_to_date_median: number
    season_status: string
    this_season_by_month: number[]
  }
  /** The last seven days against the same days of earlier seasons and the busiest week on record. */
  last_week: {
    from: string
    to: string
    total: number
    median: number
    status: string
    record_total: number
    record_from: string | null
    record_to: string | null
  }
}

/** [latitude, longitude, date, fire radiative power in MW] */
export type HotspotPoint = [number, number, string, number]

export interface Hotspots {
  /** Every detection by every sensor in the selection. The CSV has this many rows. */
  detections: number
  /** Detections that make up the harmonized series. */
  total: number
  shown: number
  points: HotspotPoint[]
}

/** Detections per sensor as recorded, before any conversion. */
export interface RawCalendar {
  months: number[]
  sensors: Record<string, { seasons: number[]; counts: number[][]; total: number; first_date: string; last_date: string }>
}

export interface Health {
  hotspots: number
  first_date: string
  last_date: string
}

export interface Method {
  viirs_start: string
  aqua_start: string
  snpp_end: string
  overlap_seasons: [number, number]
  noaa20_factor: number
  confidence_check: { rule: string; dropped_share: number; national_season: number; region_season: number }[]
  eras: {
    modis: {
      overall_factor: number
      month_factor: Record<string, number>
      interval: [number, number]
      /** Fitted exponent on the MODIS count. Below 1, so busier months convert at a lower rate. */
      count_model: { exponent: number }
      /** Share of VIIRS detections in months where MODIS saw nothing, which no conversion can recover. */
      missed_where_modis_saw_nothing: number
      /** Held-out error of the two baselines and of the regression in use. */
      validation: Record<string, { single_factor: number; month_and_region: number; count_model: number }>
      held_out_seasons: { season: number; predicted: number; observed: number }[]
    }
    terra: {
      terra_to_modis: number
      fitted_on_seasons: [number, number]
      tested_on_seasons: [number, number]
      validation: { national_season: number; region_season: number }
      interval: [number, number]
    }
  }
}

async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    const detail = await response.json().then(
      (b) => b.detail,
      () => null,
    )
    throw new Error(typeof detail === 'string' ? detail : `The server answered ${response.status}.`)
  }
  return response.json()
}

export const getHealth = () => request<Health>('/api/health')
export const getAreas = () => request<{ regions: RegionInfo[] }>('/api/areas')
export const getMethod = () => request<Method>('/api/method')
export const getBoundaries = (level: 'adm1' | 'adm2') => request<GeoJSON.FeatureCollection>(`/api/boundaries/${level}`)
export const getSummary = (query: Query, signal: AbortSignal) => request<Summary>('/api/summary', query, signal)
export const getRaw = (area: Area, signal: AbortSignal) => request<RawCalendar>('/api/calendar', { area, start: null, end: null }, signal)
export const getHotspots = (query: Query, signal: AbortSignal) => request<Hotspots>('/api/hotspots', query, signal)

/** `hotspots` is every detection in the selection. `calendar` is the harmonized count per month with its anomaly. */
export async function downloadCsv(query: Query, kind: 'hotspots' | 'calendar'): Promise<void> {
  const response = await fetch(`/api/${kind}.csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(query),
  })
  if (!response.ok) throw new Error(`The download failed (${response.status}).`)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = kind === 'hotspots' ? 'gambia_hotspots.csv' : 'gambia_burning_calendar.csv'
  link.click()
  URL.revokeObjectURL(url)
}
