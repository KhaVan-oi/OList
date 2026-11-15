import type { SVGProps } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { chartGrid, chartSales, chartTick } from '../../../lib/chart.ts'
import { axisMoney, money } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'

const LABEL_WIDTH = 120
const LABEL_PAD = 4

export function PlaceChart({
  rows,
  onOpen,
}: {
  rows: Array<Row & { label: string }>
  onOpen?: (row: Row) => void
}) {
  const tip = (value: unknown) => money(typeof value === 'number' ? value : Number(value))
  if (rows.length === 0) {
    return <p className="flex h-72 items-center text-sm text-muted-foreground">Không có dòng.</p>
  }
  const height = Math.max(288, rows.length * 36)
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid horizontal={false} stroke={chartGrid} />
          <XAxis type="number" tickFormatter={axisMoney} tick={{ fill: chartTick, fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="label"
            width={LABEL_WIDTH}
            interval={0}
            tick={<LeftLabel />}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip formatter={tip} />
          <Bar
            dataKey="revenue"
            name="Doanh thu hàng"
            fill={chartSales}
            barSize={16}
            radius={[0, 6, 6, 0]}
            cursor={onOpen ? 'pointer' : 'default'}
            onClick={click(onOpen)}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function LeftLabel({
  x = 0,
  y = 0,
  payload,
}: SVGProps<SVGTextElement> & { payload?: { value?: string } }) {
  const label = String(payload?.value ?? '')
  return (
    <text
      x={Number(x) - LABEL_WIDTH + LABEL_PAD}
      y={Number(y)}
      dy={4}
      textAnchor="start"
      fill={chartTick}
      fontSize={11}
    >
      {clip(label, 16)}
      <title>{label}</title>
    </text>
  )
}

function clip(value: string, max: number) {
  if (value.length <= max) return value
  return `${value.slice(0, max - 1)}…`
}

function click(onOpen?: (row: Row) => void) {
  return (item: unknown) => {
    const row = (item as { payload?: Row }).payload
    if (onOpen && row) onOpen(row)
  }
}
