import type { ReactElement } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'
import { chartFreight, chartGrid, chartSales, chartTick, chartYears } from '../../../lib/chart.ts'
import { axisMoney, money, count, pct } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import type { KpiValue, Operation } from '../depth.ts'

const tick = { fill: chartTick, fontSize: 11 }

const MONTH_VI = [
  'Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4',
  'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8',
  'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12',
]

function formatTip(value: unknown, activeKpi: KpiValue): string {
  const n = typeof value === 'number' ? value : Number(value)
  if (activeKpi === 'count') return count(n)
  return money(n)
}

function axisFormatter(activeKpi: KpiValue) {
  return (v: number) => (activeKpi === 'count' ? String(v) : axisMoney(v))
}

const KPI_NAME: Record<KpiValue, string> = {
  sales: 'Doanh thu',
  freight: 'Phí vận chuyển',
  count: 'Số lượng',
}

const GROWTH_NAME = 'Tăng trưởng (%)'

/** Tên cột tăng trưởng của measure đang xem, theo cấp có sẵn trong dữ liệu (mom | qoq | yoy) */
function growthKeyOf(row: Row | undefined, activeKpi: KpiValue): string | null {
  if (!row) return null
  const suffix =
    activeKpi === 'sales' ? 'product_sales_pct' : activeKpi === 'freight' ? 'freight_value_pct' : 'order_item_count_pct'
  for (const prefix of ['mom', 'qoq', 'yoy']) {
    if (`${prefix}_product_sales_pct` in row) return `${prefix}_${suffix}`
  }
  return null
}

export function TimeChart({
  rows,
  operation,
  activeKpi,
  canDrill,
  onDrill,
  heightClass = 'h-72',
  showGrowth = true,
}: {
  rows: Array<Row & { label: string }>
  operation: Operation
  activeKpi: KpiValue
  canDrill: boolean
  onDrill: (row: Row) => void
  heightClass?: string
  /** false: chỉ vẽ cột, bỏ đường tăng trưởng (dùng cho biểu đồ thu nhỏ, hai trục khó đọc) */
  showGrowth?: boolean
}) {
  const kpiKey =
    activeKpi === 'sales' ? 'product_sales' : activeKpi === 'freight' ? 'freight_value' : 'order_item_count'

  // Nhấn ở bất kỳ vị trí nào trong dải của cột đều drill, kể cả cột rất thấp (vd. năm 2016)
  const handleChartClick = (state: unknown) => {
    if (!canDrill) return
    const index = Number((state as { activeTooltipIndex?: number | string } | undefined)?.activeTooltipIndex)
    const row = Number.isInteger(index) ? rows[index] : undefined
    if (row) onDrill(row)
  }
  const chartStyle = { cursor: canDrill ? 'pointer' : 'default' }

  if (rows.length === 0) {
    return (
      <div className={`flex ${heightClass} flex-col items-center justify-center gap-2 text-sm text-muted-foreground`}>
        <span className="text-2xl">📭</span>
        <span>Không có dữ liệu cho bộ lọc đã chọn</span>
      </div>
    )
  }

  /* ── Pivot: bar chart 3 năm ── */
  if (operation === 'pivot') {
    const tipFormatter = (value: unknown) => formatTip(value, activeKpi)
    const pivotRows = rows.map((r) => ({
      ...r,
      label: MONTH_VI[(Number(r.month) - 1)] ?? r.label,
    }))
    return (
      <ChartFrame heightClass={heightClass}>
        <BarChart data={pivotRows}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="label" tick={tick} />
          <YAxis tickFormatter={axisFormatter(activeKpi)} width={56} tick={tick} />
          <Tooltip formatter={tipFormatter} />
          <Legend />
          <Bar dataKey="val_2016" name="2016" fill={chartYears[0]} radius={[4, 4, 0, 0]} />
          <Bar dataKey="val_2017" name="2017" fill={chartYears[1]} radius={[4, 4, 0, 0]} />
          <Bar dataKey="val_2018" name="2018" fill={chartYears[2]} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ChartFrame>
    )
  }

  /* ── Dice (nhiều năm, nhóm theo năm/quý/tháng/ngày): chỉ measure đang chọn ── */
  if (operation === 'dice') {
    return (
      <ChartFrame heightClass={heightClass}>
        <BarChart data={rows}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="label" tick={tick} interval="preserveStartEnd" />
          <YAxis tickFormatter={axisFormatter(activeKpi)} width={56} tick={tick} />
          <Tooltip formatter={(v: unknown) => formatTip(v, activeKpi)} />
          <Bar dataKey={kpiKey} name={KPI_NAME[activeKpi]} fill={chartSales} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ChartFrame>
    )
  }

  /* ── Timeanalysis: cột measure đang chọn + đường tăng trưởng của chính measure đó ── */
  const growthKey = growthKeyOf(rows[0], activeKpi)
  const growthPoints = growthKey == null ? 0 : rows.filter((r) => r[growthKey] != null).length
  const hasGrowth = showGrowth && growthKey != null && growthPoints > 0

  if (hasGrowth) {
    return (
      <ChartFrame heightClass={heightClass}>
        <ComposedChart data={rows} style={chartStyle} onClick={handleChartClick}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="label" tick={tick} interval="preserveStartEnd" />
          <YAxis yAxisId="left" tickFormatter={axisFormatter(activeKpi)} width={56} tick={tick} />
          <YAxis yAxisId="right" orientation="right" tickFormatter={(v: number) => `${v}%`} width={56} tick={tick} />
          <Tooltip
            formatter={(value: unknown, name: unknown) => {
              const n = typeof value === 'number' ? value : Number(value)
              if (name === GROWTH_NAME) return pct(n)
              return formatTip(n, activeKpi)
            }}
          />
          <Legend />
          <Bar yAxisId="left" dataKey={kpiKey} name={KPI_NAME[activeKpi]} fill={chartSales} radius={[4, 4, 0, 0]} />
          <Line
            yAxisId="right"
            dataKey={growthKey}
            name={GROWTH_NAME}
            stroke={chartFreight}
            dot={growthPoints < 2 ? { r: 4 } : false}
            strokeWidth={2}
            connectNulls={false}
          />
        </ComposedChart>
      </ChartFrame>
    )
  }

  // Cấp ngày hoặc chưa có dữ liệu tăng trưởng: chỉ cột
  return (
    <ChartFrame heightClass={heightClass}>
      <BarChart data={rows} style={chartStyle} onClick={handleChartClick}>
        <CartesianGrid vertical={false} stroke={chartGrid} />
        <XAxis dataKey="label" tick={tick} interval="preserveStartEnd" />
        <YAxis tickFormatter={axisFormatter(activeKpi)} width={56} tick={tick} />
        <Tooltip formatter={(v: unknown) => formatTip(v, activeKpi)} />
        <Bar dataKey={kpiKey} name={KPI_NAME[activeKpi]} fill={chartSales} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartFrame>
  )
}

function ChartFrame({ children, heightClass }: { children: ReactElement; heightClass: string }) {
  return (
    <div className={heightClass}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  )
}
