import { getJson } from '../../../lib/http.ts'
import type { ListResponse } from '../../../types/api.ts'
import type { OverviewResponse } from '../types/overview.ts'

export function getOverview() {
  return getJson<OverviewResponse>('/api/overview')
}

export function getMonthBrief() {
  return getJson<ListResponse>('/api/sales-time/monthly')
}

export function getCategoryBrief() {
  return getJson<ListResponse>('/api/product-geo/categories?limit=5')
}

export function getCustomerBrief() {
  return getJson<ListResponse>('/api/customer-payment/frequency')
}

export function getParetoBrief() {
  return getJson<ListResponse>('/api/product-geo/pareto')
}
