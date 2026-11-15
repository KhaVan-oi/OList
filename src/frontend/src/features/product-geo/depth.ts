import type { Row } from '../../types/api.ts'

export const PAGE_SIZE = 10
/** Hạng trong bang: mặc định top 5; xem thêm → tối đa RANK_ALL. */
export const RANK_TOP = 5
export const RANK_ALL = 200

export function stateOf(params: URLSearchParams) {
  const value = (params.get('state') ?? '').trim().toUpperCase()
  return /^[A-Z]{2}$/.test(value) ? value : ''
}

/** Đủ bang khách có đơn delivered trong kho (27). */
export const diceStateChoices = [
  'AC',
  'AL',
  'AM',
  'AP',
  'BA',
  'CE',
  'DF',
  'ES',
  'GO',
  'MA',
  'MG',
  'MS',
  'MT',
  'PA',
  'PB',
  'PE',
  'PI',
  'PR',
  'RJ',
  'RN',
  'RO',
  'RR',
  'RS',
  'SC',
  'SE',
  'SP',
  'TO',
]

export function categoryOf(params: URLSearchParams) {
  return (params.get('category') ?? '').trim()
}

/** Đủ danh mục trong bang (sau «Xem thêm»). */
export function fullRanksOf(params: URLSearchParams) {
  return params.get('full') === '1'
}

export function yearOf(params: URLSearchParams) {
  const value = params.get('year')
  if (value == null || value.trim() === '') return ''
  const year = Number(value)
  return year === 2016 || year === 2017 || year === 2018 ? String(year) : ''
}

export function quarterOf(params: URLSearchParams) {
  const value = params.get('quarter')
  if (value == null || value.trim() === '') return ''
  const quarter = Number(value)
  return quarter >= 1 && quarter <= 4 ? String(quarter) : ''
}

export function periodQueryOf(year: string, quarter: string) {
  const parts: string[] = []
  if (year) parts.push(`year=${encodeURIComponent(year)}`)
  if (year && quarter) parts.push(`quarter=${encodeURIComponent(quarter)}`)
  return parts.join('&')
}

export function periodLabel(year: string, quarter: string) {
  if (!year) return 'Toàn kỳ'
  if (!quarter) return `Năm ${year}`
  return `${year} Q${quarter}`
}

export function diceStatesOf(params: URLSearchParams) {
  const raw = params.get('box')
  if (raw == null || raw.trim() === '') return ['SP', 'RJ', 'MG']
  const states = raw.split(',').map((item) => item.trim().toUpperCase()).filter((item) => diceStateChoices.includes(item))
  return states.length ? states : ['SP', 'RJ', 'MG']
}

export function topOf(params: URLSearchParams) {
  const value = params.get('top') ?? '10'
  return value === '5' || value === '20' ? value : '10'
}

export function pageOf(params: URLSearchParams, total: number, key = 'page') {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const requested = Number(params.get(key) ?? '1')
  const page = Number.isInteger(requested) && requested > 0 ? requested : 1
  return { page: Math.min(page, pages), pages }
}

export function sellerLabel(value: Row[string]) {
  return typeof value === 'string' ? value.slice(0, 8) : ''
}

export function pretty(value: string) {
  return value.replaceAll('_', ' ')
}

export function numberOf(value: Row[string] | undefined) {
  return typeof value === 'number' ? value : null
}
