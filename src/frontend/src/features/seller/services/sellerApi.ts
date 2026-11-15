import { getJson } from '../../../lib/http.ts'
import type { ListResponse } from '../../../types/api.ts'

function withPeriod(query: URLSearchParams, year: string, quarter: string) {
  if (year) query.set('year', year)
  if (year && quarter) query.set('quarter', quarter)
  return query
}

export function getSellerCategories(year = '', quarter = '') {
  const query = withPeriod(new URLSearchParams({ limit: '200' }), year, quarter)
  return getJson<ListResponse>(`/api/product-geo/categories?${query}`)
}

export function getSellerPeriods() {
  return getJson<ListResponse & { years?: number[] }>('/api/product-geo/periods')
}

export function getTopSellers(top: string, category: string, year = '', quarter = '', states: string[] = []) {
  const query = withPeriod(new URLSearchParams({ limit: top }), year, quarter)
  if (category) query.set('category', category)
  if (states.length) query.set('states', states.join(','))
  return getJson<ListResponse>(`/api/product-geo/sellers?${query}`)
}

export function getSellerDice(top: string, categories: string[], states: string[], year = '', quarter = '') {
  const query = withPeriod(
    new URLSearchParams({
      limit: top,
      category: categories.join(','),
      states: states.join(','),
    }),
    year,
    quarter,
  )
  return getJson<ListResponse>(`/api/product-geo/dice?${query}`)
}
