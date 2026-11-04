import type { Row } from '../../types/api.ts'

export const DRILL_MAX = 4

export const operations = [
  ['drill', 'Khoan'],
  ['summary', 'Tổng'],
  ['rollup', 'Cuộn'],
  ['slice', 'Lát'],
  ['dice', 'Khối'],
  ['pivot', 'Xoay'],
] as const

export type Operation = (typeof operations)[number][0]

export const rollupLevels = [
  { level: 7, depth: 1, label: 'Tổng' },
  { level: 3, depth: 2, label: 'Năm' },
  { level: 1, depth: 3, label: 'Quý' },
  { level: 0, depth: 4, label: 'Tháng' },
] as const

export function operationOf(params: URLSearchParams): Operation {
  const value = params.get('op')
  if (operations.some(([id]) => id === value)) return value as Operation
  return 'drill'
}

export function drillDepth(params: URLSearchParams) {
  if (params.get('month')) return 4
  if (params.get('quarter')) return 3
  if (params.get('year')) return 2
  return 1
}

export function endpointFor(params: URLSearchParams) {
  const op = operationOf(params)
  if (op === 'summary') {
    const grain = params.get('grain') ?? 'month'
    if (grain === 'quarter') return '/api/sales-time/quarterly'
    if (grain === 'year') return '/api/sales-time/yearly'
    return '/api/sales-time/monthly'
  }
  if (op === 'rollup') return '/api/sales-time/rollup'
  if (op === 'drill') {
    const query = new URLSearchParams()
    for (const key of ['year', 'quarter', 'month', 'weekend']) {
      const value = params.get(key)
      if (value) query.set(key, value)
    }
    const suffix = query.toString()
    return suffix ? `/api/sales-time/drilldown?${suffix}` : '/api/sales-time/drilldown'
  }
  if (op === 'slice') return `/api/sales-time/slice?year=${params.get('year') ?? '2017'}`
  if (op === 'dice') {
    const query = new URLSearchParams({
      year_from: params.get('year_from') ?? '2016',
      year_to: params.get('year_to') ?? '2018',
    })
    for (const key of ['quarter', 'month', 'weekend']) {
      const value = params.get(key)
      if (value) query.set(key, value)
    }
    return `/api/sales-time/dice?${query}`
  }
  return `/api/sales-time/pivot?kpi=${params.get('kpi') ?? 'sales'}&type=${params.get('type') ?? 'value'}`
}

export function paramsFor(op: Operation) {
  const next = new URLSearchParams({ op })
  if (op === 'summary') next.set('grain', 'month')
  if (op === 'rollup') next.set('level', '3')
  if (op === 'slice') next.set('year', '2017')
  if (op === 'dice') {
    next.set('year_from', '2016')
    next.set('year_to', '2018')
    next.set('quarter', '4')
    next.set('weekend', '1')
  }
  if (op === 'pivot') {
    next.set('kpi', 'sales')
    next.set('type', 'value')
  }
  return next
}

export function climbTo(params: URLSearchParams, depth: number) {
  const next = new URLSearchParams(params)
  next.set('op', 'drill')
  if (depth <= 1) next.delete('year')
  if (depth <= 2) next.delete('quarter')
  if (depth <= 3) {
    next.delete('month')
    next.delete('weekend')
  }
  return next
}

export function drillInto(params: URLSearchParams, row: Row) {
  const depth = drillDepth(params)
  if (depth >= DRILL_MAX) return params
  const next = new URLSearchParams(params)
  next.set('op', 'drill')
  next.delete('weekend')
  if (depth === 1) next.set('year', String(row.year))
  if (depth === 2) next.set('quarter', String(row.quarter))
  if (depth === 3) next.set('month', String(row.month))
  return next
}

export function rowLabel(row: Row, op: Operation) {
  if (typeof row.full_date === 'string') return row.full_date.slice(5)
  if (op === 'pivot') return `T${row.month}`
  if (op === 'rollup') {
    if (row.grouping_level === 7) return 'Tổng'
    if (row.grouping_level === 3) return String(row.year)
    if (row.grouping_level === 1) return `Q${row.quarter}/${row.year}`
    return `${row.month}/${row.year}`
  }
  if (row.quarter != null && row.month == null) return `Q${row.quarter}`
  if (row.month != null && row.year != null) return `${row.month}/${row.year}`
  if (row.month != null) return `T${row.month}`
  if (row.year != null) return String(row.year)
  return ''
}
