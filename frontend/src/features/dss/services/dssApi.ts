import { getJson } from '../../../lib/http.ts'

export type DssScope = 'total' | 'state' | 'category'
export type DssMetric = 'units' | 'revenue'
export type ModelName = 'blend' | 'naive' | 'ma3' | 'holt'
export type DssModel = ModelName

export type DssSelection = {
  scope: DssScope
  value: string
  metric: DssMetric
  model: DssModel
  service: string
  excludeEvent: boolean
}

export type DssOptions = {
  status: string
  first_month: string
  last_month: string
  next_month: string
  event_months: string[]
  states: { code: string; units: number; revenue: number }[]
  categories: { category: string; units: number; revenue: number }[]
}

export type ModelMetric = {
  model: ModelName
  wape: number | null
  mape: number | null
  bias: number | null
  wape_ex_event: number | null
  n: number
}

export type BacktestRow = { month: string; actual: number; chosen: number } & Record<ModelName, number>

export type TradeoffRow = {
  service: number
  stockout_rate: number | null
  overstock_pct: number | null
  shortfall_pct: number | null
  n: number
}

export type DssForecast = {
  status: string
  scope: DssScope
  value: string | null
  metric: DssMetric
  service: number
  exclude_event: boolean
  window: { first: string; last: string; next: string }
  history: { month: string; actual: number }[]
  backtest: BacktestRow[]
  metrics: ModelMetric[]
  chosen_model: ModelName
  next: { month: string; forecast: number; by_model: Record<ModelName, number> }
  /** `buffer` là đệm đúng đơn vị của chỉ số (món hoặc R$). `buffer_pct` chỉ để hiển thị. */
  order: {
    service: number
    quantity: number
    buffer: number
    buffer_pct: number
    n_errors: number
  }
  tradeoff: TradeoffRow[]
  note: string
}

export type AccuracyLevel = {
  level: string
  n_series: number
  models: { model: ModelName; wape: number | null; wape_ex_event: number | null }[]
  series: { name: string; wape: number | null; wape_naive: number | null }[]
}

export type DssAccuracy = {
  status: string
  metric: DssMetric
  levels: AccuracyLevel[]
  test_window: { first: string; last: string; n_months: number }
  event_months: string[]
  note: string
}

function scopeQuery(selection: DssSelection) {
  const query = new URLSearchParams({ scope: selection.scope })
  if (selection.scope !== 'total' && selection.value) query.set('value', selection.value)
  query.set('service', selection.service)
  query.set('model', selection.model)
  if (selection.excludeEvent) query.set('exclude_event', '1')
  return query
}

export function getDssOptions() {
  return getJson<DssOptions>('/api/dss/options')
}

export function getDssForecast(selection: DssSelection) {
  const query = scopeQuery(selection)
  query.set('metric', selection.metric)
  return getJson<DssForecast>(`/api/dss/forecast?${query}`)
}

export function getDssAccuracy(metric: DssMetric) {
  return getJson<DssAccuracy>(`/api/dss/accuracy?metric=${metric}`)
}
