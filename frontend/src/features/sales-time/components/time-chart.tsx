import type { ReactElement } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { chartFreight, chartGrid, chartSales, chartTick, chartYears } from '../../../lib/chart.ts'
import { axisMoney, money } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import type { Operation } from '../depth.ts'

const tick = { fill: chartTick, fontSize: 11 }

export function TimeChart({
  rows,
  operation,
  canDrill,
  onDrill,
}: {
  rows: Array<Row & { label: string }>
  operation: Operation
  canDrill: boolean
  onDrill: (row: Row) => void
}) {
  const tip = (value: unknown) => money(typeof value === 'number' ? value : Number(value))
  const open = (state: unknown) => {
    const row = payloadOf(state)
    if (canDrill && row) onDrill(row)
  }

  if (rows.length === 0) {
    return <p className="flex h-72 items-center text-sm text-muted-foreground">Không có dòng.</p>
  }

  if (operation === 'pivot') {
    return (
      <ChartFrame>
        <BarChart data={rows}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="label" tick={tick} />
          <YAxis tickFormatter={axisMoney} width={48} tick={tick} />
          <Tooltip formatter={tip} />
          <Bar dataKey="val_2016" name="2016" fill={chartYears[0]} radius={[6, 6, 0, 0]} />
          <Bar dataKey="val_2017" name="2017" fill={chartYears[1]} radius={[6, 6, 0, 0]} />
          <Bar dataKey="val_2018" name="2018" fill={chartYears[2]} radius={[6, 6, 0, 0]} />
        </BarChart>
      </ChartFrame>
    )
  }

  if (operation === 'summary' || operation === 'slice') {
    return (
      <ChartFrame>
        <LineChart data={rows}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="label" tick={tick} interval="preserveStartEnd" />
          <YAxis tickFormatter={axisMoney} width={48} tick={tick} />
          <Tooltip formatter={tip} />
          <Line dataKey="product_sales" name="Doanh thu hàng" stroke={chartSales} dot={false} strokeWidth={2} cursor={canDrill ? 'pointer' : 'default'} onClick={open} />
          <Line dataKey="freight_value" name="Cước" stroke={chartFreight} dot={false} strokeWidth={2} />
        </LineChart>
      </ChartFrame>
    )
  }

  return (
    <ChartFrame>
      <BarChart data={rows}>
        <CartesianGrid vertical={false} stroke={chartGrid} />
        <XAxis dataKey="label" tick={tick} interval="preserveStartEnd" />
        <YAxis tickFormatter={axisMoney} width={48} tick={tick} />
        <Tooltip formatter={tip} />
        <Bar
          dataKey="product_sales"
          name="Doanh thu hàng"
          fill={chartSales}
          radius={[6, 6, 0, 0]}
          cursor={canDrill ? 'pointer' : 'default'}
          onClick={open}
        />
      </BarChart>
    </ChartFrame>
  )
}

function ChartFrame({ children }: { children: ReactElement }) {
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
    </div>
  )
}

function payloadOf(state: unknown) {
  if (state && typeof state === 'object' && 'payload' in state) return (state as { payload?: Row }).payload
  return undefined
}
