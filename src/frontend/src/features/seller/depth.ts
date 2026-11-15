import type { Row } from '../../types/api.ts'

/** Đủ bang khách có đơn delivered trong kho (27). */
export const allCustomerStates = [
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
] as const

export const diceStateChoices = allCustomerStates
export const defaultDiceStates = ['SP', 'RJ', 'MG'] as const
export const defaultDiceCategory = 'health_beauty'

export function categoryOf(params: URLSearchParams) {
  return (params.get('category') ?? '').trim()
}

/** Nhiều danh mục trên mặt khối (dice), cách nhau bởi dấu phẩy. */
export function diceCategoriesOf(params: URLSearchParams) {
  return (params.get('category') ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

/** Bang mặt khối (dice). Rỗng = chưa dice, đang xếp hạng. */
export function diceStatesOf(params: URLSearchParams) {
  const raw = params.get('box')
  if (raw == null || raw.trim() === '') return [] as string[]
  return raw
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter((item): item is (typeof diceStateChoices)[number] => (diceStateChoices as readonly string[]).includes(item))
}

/** Bang lát trên xếp hạng (filter). Khác `box` của dice. */
export function filterStatesOf(params: URLSearchParams) {
  const raw = params.get('states')
  if (raw == null || raw.trim() === '') return [] as string[]
  return raw
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter((item): item is (typeof diceStateChoices)[number] => (diceStateChoices as readonly string[]).includes(item))
}

export function topOf(params: URLSearchParams) {
  const value = params.get('top') ?? '10'
  return value === '5' || value === '20' ? value : '10'
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

export function focusOf(params: URLSearchParams) {
  const value = (params.get('focus') ?? '').trim().toLowerCase()
  return /^[0-9a-f]{32}$/.test(value) ? value : ''
}

/** Focus một bang trong khối (đối xứng focus seller). */
export function focusStateOf(params: URLSearchParams) {
  const value = (params.get('fstate') ?? '').trim().toUpperCase()
  return (diceStateChoices as readonly string[]).includes(value) ? value : ''
}

/** Focus một danh mục trong khối. */
export function focusCategoryOf(params: URLSearchParams) {
  return (params.get('fcat') ?? '').trim()
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

/** Cho phép rỗng (bỏ hết bang → về xếp hạng). */
export function toggleCode(selected: string[], code: string) {
  const next = selected.includes(code) ? selected.filter((item) => item !== code) : [...selected, code]
  return next.join(',')
}

export function periodLabel(year: string, quarter: string) {
  if (!year) return 'Toàn kỳ'
  if (!quarter) return `Năm ${year}`
  return `${year} Q${quarter}`
}
