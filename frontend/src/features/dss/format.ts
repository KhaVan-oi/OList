import { count, money, pct } from '../../lib/format.ts'
import type { DssMetric } from './services/dssApi.ts'

/** Tỷ lệ 0..1 hiển thị theo phần trăm của ứng dụng. */
export const ratio = (value: number | null | undefined) => (value == null ? 'Trống' : pct(value * 100))

/** Phần trăm đã nhân 100 (ví dụ đổi lợi nhuận). Có dấu + khi dương. */
export const signedPct = (value: number | null | undefined) => {
  if (value == null) return 'Trống'
  if (Math.abs(value) < 0.005) return pct(0)
  return `${value > 0 ? '+' : ''}${pct(value)}`
}

export const categoryLabel = (code: string) => code.replaceAll('_', ' ')

export function formatMetric(metric: DssMetric, value: number | null | undefined) {
  if (value == null) return 'Trống'
  return metric === 'units' ? count(Math.round(value)) : money(value)
}

const oneDecimal = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 })

/** Nhận xét một câu: mô hình đang dùng so với baseline "tháng trước", tính bằng điểm phần trăm WAPE. */
export function baselineVerdict(model: string, wape: number | null | undefined, baseline: number | null | undefined) {
  if (model === 'naive') return 'Đang dùng chính mô hình baseline.'
  if (wape == null || baseline == null) return ''
  const gain = (baseline - wape) * 100
  if (gain > 2) return `Mô hình tốt hơn baseline ${oneDecimal.format(gain)} điểm phần trăm.`
  if (gain >= 0.5) return `Mô hình chỉ hơn baseline ${oneDecimal.format(gain)} điểm phần trăm.`
  if (gain > -0.5) return 'Mô hình ngang baseline.'
  return `Mô hình kém baseline ${oneDecimal.format(-gain)} điểm phần trăm.`
}

export const units =(value: number | null | undefined) => (value == null ? 'Trống' : count(Math.round(value)))
