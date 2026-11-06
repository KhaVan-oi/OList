import { getJson } from '../../../lib/http.ts'
import type { ListResponse, Row } from '../../../types/api.ts'

export type DrillResponse = ListResponse & { total?: Row; level?: number }

export function getFrequency() {
  return getJson<ListResponse>('/api/customer-payment/frequency')
}

/** Roll-up / drill-down: query lấy từ drilldownQuery() trong depth.ts */
export function getCustomerDrilldown(query: string) {
  return getJson<DrillResponse>(`/api/customer-payment/drilldown?${query}`)
}

/** Ma trận Bang × Năm của mọi khách delivered. states rỗng = tất cả bang. */
export function getCustomerMatrix(states: string[] = []) {
  const query = new URLSearchParams({ year_from: '2016', year_to: '2018' })
  if (states.length) query.set('states', states.join(','))
  return getJson<ListResponse>(`/api/customer-payment/matrix?${query}`)
}

/** Dice: bang × năm × khách mua lại */
export function getCustomerDice(states: string[], yearFrom: string, yearTo: string) {
  const query = new URLSearchParams({ states: states.join(','), year_from: yearFrom, year_to: yearTo })
  return getJson<ListResponse>(`/api/customer-payment/dice?${query}`)
}

/** Top 3 khách chi nhiều nhất theo bang (DENSE_RANK) + phân vị toàn quốc (PERCENT_RANK) */
export function getCustomerRanking(states: string[] = []) {
  const query = new URLSearchParams()
  if (states.length) query.set('states', states.join(','))
  return getJson<ListResponse>(`/api/customer-payment/ranking?${query}`)
}
