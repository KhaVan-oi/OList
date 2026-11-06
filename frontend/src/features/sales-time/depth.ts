import type { Row } from '../../types/api.ts'

// Độ sâu tối đa khi drill: Năm(1) → Quý(2) → Tháng(3) → Ngày(4)
export const DRILL_MAX = 4

export type Operation = 'timeanalysis' | 'dice' | 'pivot'

export function operationOf(params: URLSearchParams): Operation {
  const op = params.get('op')
  if (op === 'dice') return 'dice'
  if (op === 'pivot') return 'pivot'
  return 'timeanalysis'
}

/** Cấp hiển thị trong timeanalysis: year | quarter | month | day */
export type TimeLevel = 'year' | 'quarter' | 'month' | 'day'

/**
 * Cấp của biểu đồ suy ra từ bộ lọc phân cấp (Toàn kỳ → Năm → Quý → Tháng):
 * biểu đồ luôn hiện các con của lựa chọn sâu nhất. Nhờ đó nhấn cột và dùng bộ lọc
 * cho cùng một kết quả.
 */
export function timeLevelOf(params: URLSearchParams): TimeLevel {
  if (params.get('year')) {
    if (!params.get('quarter')) return 'quarter'
    if (!params.get('month')) return 'month'
    return 'day'
  }
  return 'year'
}

/** Nhóm theo của chế độ Nhiều năm (Dice) */
export type DiceGroup = 'year' | 'quarter' | 'month' | 'day'

export function diceGroupOf(params: URLSearchParams): DiceGroup {
  const value = params.get('group_by')
  return value === 'quarter' || value === 'month' || value === 'day' ? value : 'year'
}

/** Bộ lọc Dice hiển thị theo Nhóm theo: Năm < Quý < Tháng < Ngày */
export const DICE_GROUP_RANK: Record<DiceGroup, number> = { year: 0, quarter: 1, month: 2, day: 3 }

/** Tháng thuộc một quý (rỗng = cả 12 tháng) */
export function monthsOfQuarter(quarter: string): number[] {
  const q = Number(quarter)
  if (q >= 1 && q <= 4) return [1, 2, 3].map((i) => (q - 1) * 3 + i)
  return Array.from({ length: 12 }, (_, i) => i + 1)
}

/** Trả URL endpoint tương ứng với trạng thái hiện tại */
export function endpointFor(params: URLSearchParams): string {
  const op = operationOf(params)

  if (op === 'dice') {
    const group = diceGroupOf(params)
    const query = new URLSearchParams({
      year_from: params.get('year_from') ?? '2016',
      year_to: params.get('year_to') ?? '2018',
      group_by: group,
    })
    for (const key of ['quarter', 'month', 'weekend']) {
      const value = params.get(key)
      if (value) query.set(key, value)
    }
    return `/api/sales-time/dice?${query}`
  }

  if (op === 'pivot') {
    return `/api/sales-time/pivot?kpi=${params.get('kpi') ?? 'sales'}&type=${params.get('type') ?? 'value'}`
  }

  // timeanalysis: cấp suy ra từ bộ lọc
  const level = timeLevelOf(params)
  const query = new URLSearchParams({ level })
  for (const key of ['year', 'quarter', 'month', 'weekend']) {
    const value = params.get(key)
    if (value) query.set(key, value)
  }
  return `/api/sales-time/timeanalysis?${query}`
}

/** Endpoint ma trận Tháng × Năm, dùng cùng bộ lọc với chế độ đang xem */
export function matrixEndpointFor(params: URLSearchParams): string {
  const query = new URLSearchParams()
  if (operationOf(params) === 'dice') {
    query.set('year_from', params.get('year_from') ?? '2016')
    query.set('year_to', params.get('year_to') ?? '2018')
  } else {
    const year = params.get('year')
    if (year) {
      query.set('year_from', year)
      query.set('year_to', year)
    }
  }
  for (const key of ['quarter', 'month', 'weekend']) {
    const value = params.get(key)
    if (value) query.set(key, value)
  }
  return `/api/sales-time/matrix?${query}`
}

/** Nhãn hiển thị cho mỗi dòng dữ liệu */
export function rowLabel(row: Row, op: Operation): string {
  if (typeof row.full_date === 'string') return row.full_date.slice(5)
  if (op === 'pivot') return `Tháng ${row.month}`
  if (row.quarter != null && row.month == null) return `Q${row.quarter}/${row.year}`
  if (row.month != null && row.year != null) return `${String(row.month).padStart(2, '0')}/${row.year}`
  if (row.month != null) return `Tháng ${row.month}`
  if (row.year != null) return String(row.year)
  return ''
}

/** KPI key → tên tiếng Việt */
export const KPI_OPTIONS = [
  { value: 'sales', label: 'Doanh thu', key: 'product_sales' },
  { value: 'freight', label: 'Phí vận chuyển', key: 'freight_value' },
  { value: 'count', label: 'Số lượng sản phẩm', key: 'order_item_count' },
] as const

export type KpiValue = (typeof KPI_OPTIONS)[number]['value']

export function kpiKeyOf(kpi: KpiValue): string {
  return KPI_OPTIONS.find((k) => k.value === kpi)?.key ?? 'product_sales'
}
