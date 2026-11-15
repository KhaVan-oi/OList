import { count, money, pct } from '../../lib/format.ts'
import type { DssMetric } from './services/dssApi.ts'

/** Tỷ lệ 0..1 hiển thị theo phần trăm của ứng dụng. */
export const ratio = (value: number | null | undefined) => (value == null ? 'Trống' : pct(value * 100))

export const categoryLabel = (code: string) => code.replaceAll('_', ' ')

export function formatMetric(metric: DssMetric, value: number | null | undefined) {
  if (value == null) return 'Trống'
  return metric === 'units' ? count(Math.round(value)) : money(value)
}

/** Số lượng có dấu (+/−), dùng cho đệm nhập hàng vốn có thể âm. */
export function signedMetric(metric: DssMetric, value: number | null | undefined) {
  if (value == null) return 'Trống'
  return `${value < 0 ? '−' : '+'}${formatMetric(metric, Math.abs(value))}`
}

const oneDecimal = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 })

/** Số thập phân một chữ số, dấu phẩy kiểu Việt Nam (17,2). */
export const decimal1 = (value: number) => oneDecimal.format(value)

const twoDecimals = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** MASE là tỷ số không đơn vị, hiển thị 2 chữ số thập phân (0,89). */
export const masePlain = (value: number | null | undefined) => (value == null ? 'Trống' : twoDecimals.format(value))

/** '2018-09' thành 'tháng 09/2018'. */
export function monthLabel(month: string) {
  const [year, mm] = month.split('-')
  return year && mm ? `tháng ${mm}/${year}` : month
}
