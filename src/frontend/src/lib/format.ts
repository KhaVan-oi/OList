const moneyFormatter = new Intl.NumberFormat('vi-VN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const countFormatter = new Intl.NumberFormat('vi-VN')

export function money(value: number | null | undefined) {
  if (value == null) return 'Trống'
  return moneyFormatter.format(value)
}

export function count(value: number | null | undefined) {
  if (value == null) return 'Trống'
  return countFormatter.format(value)
}

export function axisMoney(value: number) {
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}tr`
  if (absolute >= 1_000) return `${(value / 1_000).toFixed(2)}k`
  return value.toFixed(2)
}

export function pct(value: number | null | undefined) {
  if (value == null) return 'Trống'
  return `${new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}%`
}
