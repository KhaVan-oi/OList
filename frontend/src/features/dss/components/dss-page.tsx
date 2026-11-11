import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Badge } from '../../../components/ui/badge.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { FilterChip } from '../../../components/ui/filter-chip.tsx'
import { FilterSelect, filterBarClass } from '../../../components/ui/filter-select.tsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table.tsx'
import { chartFreight, chartGrid, chartMuted, chartSales, chartTick } from '../../../lib/chart.ts'
import { axisMoney } from '../../../lib/format.ts'
import { categoryLabel, decimal1, formatMetric, monthLabel, ratio, signedMetric } from '../format.ts'
import {
  getDssAccuracy,
  getDssForecast,
  getDssOptions,
  type DssForecast,
  type DssMetric,
  type DssModel,
  type DssScope,
  type DssSelection,
  type ModelName,
} from '../services/dssApi.ts'

const tick = { fill: chartTick, fontSize: 11 }

const MODEL_LABEL: Record<DssModel, string> = {
  blend: 'Kết hợp (khuyên dùng)',
  naive: 'Bằng tháng trước',
  ma3: 'Trung bình 3 tháng',
  holt: 'Có tính xu hướng (Holt)',
}

const MODEL_ORDER: ModelName[] = ['blend', 'naive', 'ma3', 'holt']

/** Mức an toàn: tên dễ hiểu đi kèm phân vị thật. */
const SERVICE_OPTIONS: { value: string; label: string }[] = [
  { value: '0.85', label: 'Tiết kiệm · 85%' },
  { value: '0.9', label: 'Cân bằng · 90%' },
  { value: '0.95', label: 'An toàn · 95%' },
  { value: '0.99', label: 'Rất an toàn · 99%' },
]

const metricUnit: Record<DssMetric, string> = { units: 'món', revenue: 'R$' }

export function DssPage() {
  const [selection, setSelection] = useState<DssSelection>({
    scope: 'total',
    value: '',
    metric: 'units',
    model: 'blend',
    service: '0.9',
    excludeEvent: true,
  })

  const options = useQuery({ queryKey: ['dss', 'options'], queryFn: getDssOptions })
  const forecast = useQuery({
    queryKey: ['dss', 'forecast', selection],
    queryFn: () => getDssForecast(selection),
    enabled: selection.scope === 'total' || Boolean(selection.value),
  })
  const accuracy = useQuery({
    queryKey: ['dss', 'accuracy', selection.metric],
    queryFn: () => getDssAccuracy(selection.metric),
  })

  const states = options.data?.states ?? []
  const categories = options.data?.categories ?? []
  const data = forecast.data

  function change(changes: Partial<DssSelection>) {
    setSelection((current) => ({ ...current, ...changes }))
  }

  function changeScope(scope: DssScope) {
    const value = scope === 'state' ? (states[0]?.code ?? '') : scope === 'category' ? (categories[0]?.category ?? '') : ''
    change({ scope, value })
  }

  const scopeLabel =
    selection.scope === 'total'
      ? 'Toàn kho'
      : selection.scope === 'state'
        ? `Bang ${selection.value}`
        : categoryLabel(selection.value)

  return (
    <section className="space-y-4">
      <PageHeading
        title="Quyết định nhập hàng"
        description="Tháng tới bán được bao nhiêu, và nên nhập bao nhiêu."
        actions={
          <div className={filterBarClass}>
            <FilterSelect
              id="dss-scope"
              label="Xem theo"
              minWidth="7.5rem"
              value={selection.scope}
              onChange={(value) => changeScope(value as DssScope)}
            >
              <option value="total">Toàn kho</option>
              <option value="state">Theo bang</option>
              <option value="category">Theo danh mục</option>
            </FilterSelect>
            {selection.scope === 'state' ? (
              <FilterSelect id="dss-state" label="Bang" minWidth="6.5rem" value={selection.value} onChange={(value) => change({ value })}>
                {states.map((row) => (
                  <option key={row.code} value={row.code}>{`Bang ${row.code}`}</option>
                ))}
              </FilterSelect>
            ) : null}
            {selection.scope === 'category' ? (
              <FilterSelect
                id="dss-category"
                label="Danh mục"
                minWidth="10rem"
                value={selection.value}
                onChange={(value) => change({ value })}
              >
                {categories.map((row) => (
                  <option key={row.category} value={row.category}>{categoryLabel(row.category)}</option>
                ))}
              </FilterSelect>
            ) : null}
            <FilterSelect
              id="dss-metric"
              label="Đo bằng"
              minWidth="7rem"
              value={selection.metric}
              onChange={(value) => change({ metric: value as DssMetric })}
            >
              <option value="units">Số món</option>
              <option value="revenue">Doanh thu</option>
            </FilterSelect>
            <FilterSelect
              id="dss-service"
              label="Mức an toàn"
              minWidth="9rem"
              value={selection.service}
              onChange={(value) => change({ service: value })}
            >
              {SERVICE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </FilterSelect>
          </div>
        }
      />

      <details className="group text-sm">
        <summary className="w-fit cursor-pointer text-muted-foreground select-none hover:text-foreground">
          Tùy chọn nâng cao
        </summary>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <div className={filterBarClass}>
            <FilterSelect
              id="dss-model"
              label="Cách dự báo"
              minWidth="12rem"
              value={selection.model}
              onChange={(value) => change({ model: value as DssModel })}
            >
              {MODEL_ORDER.map((model) => (
                <option key={model} value={model}>{MODEL_LABEL[model]}</option>
              ))}
            </FilterSelect>
          </div>
          <FilterChip active={selection.excludeEvent} onClick={() => change({ excludeEvent: !selection.excludeEvent })}>
            Bỏ tháng Black Friday khi tính dự phòng
          </FilterChip>
        </div>
      </details>

      <QueryState loading={forecast.isLoading} error={forecast.error}>
        {data ? (
          <>
            <AnswerCard data={data} scopeLabel={scopeLabel} />

            <div className="grid gap-4 xl:grid-cols-3">
              <Card className="xl:col-span-2">
                <CardHeader>
                  <CardTitle>Bán thực tế và dự báo</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Chấm đậm cuối cùng là lượng nên nhập cho {monthLabel(data.next.month)}.
                  </p>
                </CardHeader>
                <CardContent>
                  <ForecastChart data={data} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Chọn mức an toàn thế nào?</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Đường dọc là mức bạn đang chọn.
                  </p>
                </CardHeader>
                <CardContent>
                  <TradeoffChart rows={data.tradeoff} selected={Number(selection.service)} />
                </CardContent>
              </Card>
            </div>

            <TechnicalDetails data={data}>
              <QueryState loading={accuracy.isLoading} error={accuracy.error}>
                {accuracy.data ? (
                  <div className="space-y-2">
                    <h3 className="text-base font-semibold">Sai số theo mức chi tiết</h3>
                    <p className="text-xs text-muted-foreground">
                      Giá trị trong ngoặc là sai số khi bỏ Black Friday.
                    </p>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Mức</TableHead>
                          {MODEL_ORDER.map((model) => (
                            <TableHead key={model} className="text-right">{MODEL_LABEL[model]}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {accuracy.data.levels.map((level) => (
                          <TableRow key={level.level}>
                            <TableCell className="font-medium">{level.level}</TableCell>
                            {MODEL_ORDER.map((model) => {
                              const cell = level.models.find((item) => item.model === model)
                              return (
                                <TableCell key={model} className="text-right tabular-nums">
                                  {ratio(cell?.wape)}
                                  <span className="ml-1 text-xs text-muted-foreground">({ratio(cell?.wape_ex_event)})</span>
                                </TableCell>
                              )
                            })}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : null}
              </QueryState>
            </TechnicalDetails>
          </>
        ) : null}
      </QueryState>
    </section>
  )
}

function AnswerCard({ data, scopeLabel }: { data: DssForecast; scopeLabel: string }) {
  const unit = metricUnit[data.metric]
  const chosen = data.metrics.find((row) => row.model === data.chosen_model)
  const tradeoff = data.tradeoff.find((row) => Math.abs(row.service - data.service) < 1e-9)
  const bufferPct = `${data.order.buffer_pct >= 0 ? '+' : '−'}${decimal1(Math.abs(data.order.buffer_pct))}%`

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <p className="text-sm text-muted-foreground">
          T{monthLabel(data.next.month).slice(1)} · {scopeLabel}
        </p>
        <CardTitle className="text-2xl leading-tight sm:text-3xl">
          Nên nhập khoảng{' '}
          <span className="text-primary tabular-nums">
            {formatMetric(data.metric, data.order.quantity)} {unit}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Figure label="Dự báo bán" value={`${formatMetric(data.metric, data.next.forecast)} ${unit}`} />
          <Figure
            label="Dự phòng an toàn"
            value={`${signedMetric(data.metric, data.order.buffer)} ${unit}`}
            hint={`(${bufferPct} so với dự báo bán)`}
          />
          <Figure
            label="Dự báo thường lệch"
            value={`±${ratio(chosen?.wape)}`}
            hint={`so với thực tế, kiểm tra trên ${chosen?.n ?? 0} tháng`}
          />
        </div>

        {tradeoff?.stockout_rate != null && tradeoff.overstock_pct != null ? (
          <p className="text-sm">
            Với mức an toàn {Math.round(data.service * 100)}%, có <strong>{ratio(tradeoff.stockout_rate)}</strong> số
            tháng thiếu hàng và dư trung bình <strong>{decimal1(tradeoff.overstock_pct)}%</strong>.
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-bold tracking-tight tabular-nums">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function TechnicalDetails({ data, children }: { data: DssForecast; children: ReactNode }) {
  return (
    <details className="rounded-xl border border-border bg-card shadow-sm">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium select-none">
        Xem chi tiết kỹ thuật (so sánh cách dự báo)
      </summary>
      <div className="space-y-6 border-t border-border p-4">
        <div className="space-y-2">
          <h3 className="text-base font-semibold">So sánh các cách dự báo</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cách dự báo</TableHead>
                <TableHead className="text-right">Sai số</TableHead>
                <TableHead className="text-right">Sai số khi bỏ Black Friday</TableHead>
                <TableHead className="text-right">Lệch trung bình</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {MODEL_ORDER.map((model) => {
                const row = data.metrics.find((item) => item.model === model)
                return (
                  <TableRow key={model}>
                    <TableCell className="font-medium">
                      {MODEL_LABEL[model]}
                      {model === data.chosen_model ? <Badge variant="secondary" className="ml-2">đang dùng</Badge> : null}
                      {model === 'naive' ? <Badge variant="outline" className="ml-2">mốc so sánh</Badge> : null}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{ratio(row?.wape)}</TableCell>
                    <TableCell className="text-right tabular-nums">{ratio(row?.wape_ex_event)}</TableCell>
                    <TableCell className="text-right tabular-nums">{ratio(row?.bias)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
        {children}
      </div>
    </details>
  )
}

function ForecastChart({ data }: { data: DssForecast }) {
  const backtest = new Map(data.backtest.map((row) => [row.month, row.chosen]))
  const rows: { month: string; actual: number | null; forecast: number | null; order: number | null }[] = data.history.map(
    (point) => ({
      month: point.month,
      actual: point.actual,
      forecast: backtest.get(point.month) ?? null,
      order: null,
    }),
  )
  rows.push({ month: data.next.month, actual: null, forecast: data.next.forecast, order: data.order.quantity })
  const format = (value: unknown) => formatMetric(data.metric, Number(value))

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="month" tick={tick} />
          <YAxis tickFormatter={axisMoney} width={56} tick={tick} />
          <Tooltip formatter={format} />
          <Legend />
          <Line type="monotone" dataKey="actual" name="Thực tế" stroke={chartSales} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
          <Line
            type="monotone"
            dataKey="forecast"
            name="Dự báo"
            stroke={chartFreight}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="order"
            name="Nên nhập"
            stroke={chartMuted}
            strokeWidth={0}
            dot={{ r: 6, fill: chartSales, stroke: chartSales }}
            activeDot={{ r: 7 }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

function TradeoffChart({
  rows,
  selected,
}: {
  rows: { service: number; stockout_rate: number | null; overstock_pct: number | null }[]
  selected: number
}) {
  const label = (service: number) => `${Math.round(service * 100)}%`
  const chartRows = rows.map((row) => ({
    label: label(row.service),
    stockout: row.stockout_rate == null ? null : row.stockout_rate * 100,
    overstock: row.overstock_pct,
  }))
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartRows} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={chartGrid} />
          <XAxis dataKey="label" tick={tick} />
          <YAxis tickFormatter={(value: number) => `${value}%`} width={48} tick={tick} />
          <Tooltip formatter={(value: unknown) => `${decimal1(Number(value))}%`} />
          <Legend />
          <ReferenceLine x={label(selected)} stroke={chartTick} strokeDasharray="3 3" />
          <Line type="monotone" dataKey="stockout" name="Tháng thiếu hàng" stroke="#ff808b" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          <Line type="monotone" dataKey="overstock" name="Dư hàng trung bình" stroke={chartSales} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
