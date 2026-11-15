import type { Row } from '../../types/api.ts'
import { allCustomerStates } from '../seller/depth.ts'

export { allCustomerStates }

/** Ba chiều roll-up / drill-down của module Customer Payment */
export type Dim = 'customer' | 'geo' | 'status'

export const DIM_OPTIONS: { value: Dim; label: string }[] = [
  { value: 'customer', label: 'Khách hàng' },
  { value: 'geo', label: 'Địa lý' },
  { value: 'status', label: 'Trạng thái đơn' },
]

export function dimOf(params: URLSearchParams): Dim {
  const dim = params.get('dim')
  return dim === 'geo' || dim === 'status' ? dim : 'customer'
}

/** Mỗi measure là một cột trong dữ liệu trả về; chart và bảng chỉ hiện measure đang chọn */
export const CUSTOMER_KPIS = [
  { value: 'customers', label: 'Số khách', key: 'customers' },
  { value: 'orders', label: 'Số đơn', key: 'orders' },
  { value: 'payment', label: 'Thanh toán', key: 'payment_value' },
  { value: 'aov', label: 'AOV', key: 'aov' },
] as const

export type CustomerKpi = (typeof CUSTOMER_KPIS)[number]['value']

export function kpiOf(params: URLSearchParams): CustomerKpi {
  const kpi = params.get('kpi')
  return CUSTOMER_KPIS.some((item) => item.value === kpi) ? (kpi as CustomerKpi) : 'customers'
}

export function kpiOption(kpi: CustomerKpi) {
  return CUSTOMER_KPIS.find((item) => item.value === kpi) ?? CUSTOMER_KPIS[0]
}

export const ORDER_STATUSES = [
  'delivered',
  'shipped',
  'canceled',
  'unavailable',
  'invoiced',
  'processing',
  'created',
  'approved',
] as const

export const GROUP_OPTIONS = [
  { value: 'once', label: 'Mua một lần' },
  { value: 'repeat', label: 'Mua lại' },
] as const

export const DICE_DEFAULT_STATES = ['SP', 'RJ', 'MG']

export type CustomerMode = 'drill' | 'dice'

export function modeOf(params: URLSearchParams): CustomerMode {
  return params.get('mode') === 'dice' ? 'dice' : 'drill'
}

export function groupOf(params: URLSearchParams) {
  const group = params.get('group')
  return group === 'once' || group === 'repeat' ? group : ''
}

export function stateOf(params: URLSearchParams) {
  const state = (params.get('state') ?? '').toUpperCase()
  return (allCustomerStates as readonly string[]).includes(state) ? state : ''
}

export function statusOf(params: URLSearchParams) {
  const status = params.get('status') ?? ''
  return (ORDER_STATUSES as readonly string[]).includes(status) ? status : ''
}

export function diceStatesOf(params: URLSearchParams) {
  const raw = params.get('states')
  if (raw == null) return [...DICE_DEFAULT_STATES]
  return raw
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter((item) => (allCustomerStates as readonly string[]).includes(item))
}

/** Query string của /drilldown: chỉ gửi tham số thuộc chiều đang xem */
export function drilldownQuery(params: URLSearchParams) {
  const dim = dimOf(params)
  const query = new URLSearchParams({ dim })
  if (dim === 'customer' && groupOf(params)) query.set('group', groupOf(params))
  if (dim === 'geo' && stateOf(params)) query.set('state', stateOf(params))
  if (dim === 'status' && statusOf(params)) query.set('status', statusOf(params))
  return query.toString()
}

/** Cấp hiện tại: 0 = chưa chọn gì ở bộ lọc, 1 = đã chọn nhóm / bang / trạng thái */
export function drillLevelOf(params: URLSearchParams) {
  const dim = dimOf(params)
  if (dim === 'customer') return groupOf(params) ? 1 : 0
  if (dim === 'geo') return stateOf(params) ? 1 : 0
  return statusOf(params) ? 1 : 0
}

export function formatKpiValue(kpi: CustomerKpi, value: Row[string] | undefined, money: (n: number) => string, count: (n: number) => string) {
  if (value == null) return '—'
  const n = typeof value === 'number' ? value : Number(value)
  return kpi === 'customers' || kpi === 'orders' ? count(n) : money(n)
}
