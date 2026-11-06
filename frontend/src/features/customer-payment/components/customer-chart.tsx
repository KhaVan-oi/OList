import type { ReactElement } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { chartGrid, chartSales, chartTick, chartYears } from '../../../lib/chart.ts'
import { axisMoney, count, money } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import { kpiOption, type CustomerKpi } from '../depth.ts'

const tick = { fill: chartTick, fontSize: 11 }

function fmt(kpi: CustomerKpi, value: unknown) {
  const n = typeof value === 'number' ? value : Number(value)
  return kpi === 'customers' || kpi === 'orders' ? count(n) : money(n)
}

function axisFmt(kpi: CustomerKpi) {
  return (v: number) => (kpi === 'customers' || kpi === 'orders' ? count(v) : axisMoney(v))
}

function Frame({ heightClass, children }: { heightClass: string; children: ReactElement }) {
  return (
    <div className={heightClass}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  )
}

function Empty({ heightClass }: { heightClass: string }) {
  return (
    <div className={`flex ${heightClass} flex-col items-center justify-center gap-2 text-sm text-muted-foreground`}>
      <span className="text-2xl">📭</span>
      <span>Không có dữ liệu cho bộ lọc đã chọn</span>
    </div>
  )
}

/**
 * Cột của measure đang chọn theo các con của lựa chọn hiện tại (nhóm / bậc, bang / thành phố,
 * trạng thái / bang). Dùng chung cho tab Khách hàng và ô Khách hàng ở Tổng quan.
 */
export function CustomerChart({
  rows,
  kpi,
  canDrill = false,
  onDrill,
  heightClass = 'h-72',
}: {
  rows: Row[]
  kpi: CustomerKpi
  canDrill?: boolean
  onDrill?: (row: Row) => void
  heightClass?: string
}) {
  if (rows.length === 0) return <Empty heightClass={heightClass} />
  const option = kpiOption(kpi)
  const crowded = rows.length > 8

  // Nhấn trong dải của cột là drill, kể cả cột thấp
  const handleClick = (state: unknown) => {
    if (!canDrill || !onDrill) return
    const index = Number((state as { activeTooltipIndex?: number | string } | undefined)?.activeTooltipIndex)
    const row = Number.isInteger(index) ? rows[index] : undefined
    if (row) onDrill(row)
  }

  return (
    <Frame heightClass={heightClass}>
      <BarChart
        data={rows}
        style={{ cursor: canDrill ? 'pointer' : 'default' }}
        onClick={handleClick}
        margin={{ left: 0, right: 8, top: 4, bottom: crowded ? 24 : 0 }}
      >
        <CartesianGrid vertical={false} stroke={chartGrid} />
        <XAxis
          dataKey="label"
          tick={tick}
          interval={0}
          angle={crowded ? -40 : 0}
          textAnchor={crowded ? 'end' : 'middle'}
          height={crowded ? 56 : 30}
        />
        <YAxis tickFormatter={axisFmt(kpi)} width={56} tick={tick} />
        <Tooltip formatter={(value: unknown) => fmt(kpi, value)} />
        <Bar dataKey={option.key} name={option.label} fill={chartSales} radius={[4, 4, 0, 0]} />
      </BarChart>
    </Frame>
  )
}

/** Dice: mỗi bang một nhóm cột, mỗi năm một màu. */
export function CustomerDiceChart({
  rows,
  kpi,
  heightClass = 'h-72',
}: {
  rows: Row[]
  kpi: CustomerKpi
  heightClass?: string
}) {
  if (rows.length === 0) return <Empty heightClass={heightClass} />
  const option = kpiOption(kpi)
  const years = [...new Set(rows.map((r) => Number(r.year)))].sort()
  const byState = new Map<string, Row>()
  for (const r of rows) {
    const state = String(r.customer_state)
    const entry = byState.get(state) ?? { label: state }
    entry[`y${r.year}`] = r[option.key] ?? null
    byState.set(state, entry)
  }
  const data = [...byState.values()]

  return (
    <Frame heightClass={heightClass}>
      <BarChart data={data}>
        <CartesianGrid vertical={false} stroke={chartGrid} />
        <XAxis dataKey="label" tick={tick} />
        <YAxis tickFormatter={axisFmt(kpi)} width={56} tick={tick} />
        <Tooltip formatter={(value: unknown) => fmt(kpi, value)} />
        <Legend />
        {years.map((year) => (
          <Bar
            key={year}
            dataKey={`y${year}`}
            name={String(year)}
            fill={chartYears[year - 2016] ?? chartSales}
            radius={[4, 4, 0, 0]}
          />
        ))}
      </BarChart>
    </Frame>
  )
}
