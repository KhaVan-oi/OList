import { useQuery } from '@tanstack/react-query'
import { LightbulbIcon } from 'lucide-react'
import { useState } from 'react'
import { CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Badge } from '../../../components/ui/badge.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { FilterChip } from '../../../components/ui/filter-chip.tsx'
import { FilterSelect, filterBarClass } from '../../../components/ui/filter-select.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table.tsx'
import { chartFreight, chartGrid, chartMuted, chartSales, chartTick } from '../../../lib/chart.ts'
import { axisMoney } from '../../../lib/format.ts'
import { baselineVerdict, categoryLabel, formatMetric, ratio, signedPct } from '../format.ts'
import {
  DEFAULT_WHATIF,
  getDssAccuracy,
  getDssForecast,
  getDssOptions,
  getDssWhatIf,
  type DssForecast,
  type DssMetric,
  type DssModel,
  type DssScope,
  type DssSelection,
  type DssWhatIf,
  type ModelName,
  type WhatIfInputs,
} from '../services/dssApi.ts'
import { WhatIfPanel } from './whatif-panel.tsx'

const tick = { fill: chartTick, fontSize: 11 }

const MODEL_LABEL: Record<DssModel, string> = {
  blend: 'Kết hợp (mặc định)',
  naive: 'Tháng trước',
  ma3: 'Trung bình 3 tháng',
  holt: 'Holt',
  auto: 'Tự chọn theo WAPE',
}

const MODEL_ORDER: ModelName[] = ['blend', 'naive', 'ma3', 'holt']
const SERVICE_OPTIONS = ['0.7', '0.8', '0.9', '0.95', '0.99']

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
  const [whatIf, setWhatIf] = useState<WhatIfInputs>(DEFAULT_WHATIF)

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
  // Cùng khóa truy vấn với khối what-if bên dưới nên React Query chỉ gọi API một lần.
  const whatIfResult = useQuery({
    queryKey: ['dss', 'whatif', selection, whatIf],
    queryFn: () => getDssWhatIf(selection, whatIf),
    enabled: selection.scope === 'total' || Boolean(selection.value),
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

  const tradeoffAtService = data?.tradeoff.find((row) => Math.abs(row.service - Number(selection.service)) < 1e-9)
  const chosenMetric = data?.metrics.find((row) => row.model === data.chosen_model)
  const naiveMetric = data?.metrics.find((row) => row.model === 'naive')

  return (
    <section className="space-y-4">
      <PageHeading
        title="Hỗ trợ quyết định"
        description="Dự báo nhu cầu tháng tới, đề xuất lượng nhập và thử kịch bản khuyến mãi trên đơn delivered."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <div className={filterBarClass}>
              <LightbulbIcon className="ml-1 size-4 text-muted-foreground" />
              <FilterSelect
                id="dss-scope"
                label="Phạm vi"
                minWidth="7.5rem"
                value={selection.scope}
                onChange={(value) => changeScope(value as DssScope)}
              >
                <option value="total">Toàn kho</option>
                <option value="state">Theo bang</option>
                <option value="category">Theo danh mục</option>
              </FilterSelect>
              {selection.scope === 'state' ? (
                <FilterSelect
                  id="dss-state"
                  label="Bang"
                  minWidth="6.5rem"
                  value={selection.value}
                  onChange={(value) => change({ value })}
                >
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
                label="Đo lường"
                minWidth="7rem"
                value={selection.metric}
                onChange={(value) => change({ metric: value as DssMetric })}
              >
                <option value="units">Số món</option>
                <option value="revenue">Doanh thu hàng</option>
              </FilterSelect>
              <FilterSelect
                id="dss-model"
                label="Mô hình dự báo"
                minWidth="9.5rem"
                value={selection.model}
                onChange={(value) => change({ model: value as DssModel })}
              >
                {(['blend', 'naive', 'ma3', 'holt', 'auto'] as DssModel[]).map((model) => (
                  <option key={model} value={model}>{MODEL_LABEL[model]}</option>
                ))}
              </FilterSelect>
              <FilterSelect
                id="dss-service"
                label="Mức phục vụ"
                minWidth="8rem"
                value={selection.service}
                onChange={(value) => change({ service: value })}
              >
                {SERVICE_OPTIONS.map((value) => (
                  <option key={value} value={value}>{`Phục vụ ${Math.round(Number(value) * 100)}%`}</option>
                ))}
              </FilterSelect>
            </div>
            <FilterChip active={selection.excludeEvent} onClick={() => change({ excludeEvent: !selection.excludeEvent })}>
              Bỏ Black Friday khỏi mẫu sai số
            </FilterChip>
          </div>
        }
      />

      <QueryState loading={forecast.isLoading} error={forecast.error}>
        {data ? (
          <>
            <ConclusionCard data={data} scopeLabel={scopeLabel} whatIf={whatIfResult.data} />

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Stat
                label={`Dự báo ${data.next.month} (${metricUnit[data.metric]})`}
                value={formatMetric(data.metric, data.next.forecast)}
                detail={`${scopeLabel} · ${MODEL_LABEL[data.chosen_model]}`}
              />
              <Stat
                label="Lượng nhập đề xuất"
                value={formatMetric(data.metric, data.order.quantity)}
                detail={`Đệm ${data.order.buffer_pct >= 0 ? '+' : ''}${data.order.buffer_pct.toFixed(1)}% ở mức phục vụ ${Math.round(data.service * 100)}%`}
              />
              <Stat
                label="Sai số backtest (WAPE)"
                value={ratio(chosenMetric?.wape)}
                detail={`Baseline "tháng trước": ${ratio(naiveMetric?.wape)} · ${chosenMetric?.n ?? 0} tháng kiểm tra`}
              />
              <Stat
                label="Thiếu hàng thực nghiệm"
                value={ratio(tradeoffAtService?.stockout_rate)}
                detail={`Dư hàng trung bình ${tradeoffAtService?.overstock_pct != null ? `${tradeoffAtService.overstock_pct.toFixed(1)}%` : 'Trống'} (leave-one-out)`}
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Thực tế, dự báo và lượng nhập · {scopeLabel}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Đường đứt là dự báo trước 1 tháng ở từng tháng backtest, chỉ dùng dữ liệu trước tháng đó.
                  Điểm cuối là dự báo và lượng nhập cho {data.next.month}.
                </p>
              </CardHeader>
              <CardContent>
                <ForecastChart data={data} />
              </CardContent>
            </Card>

            <div className="grid gap-4 xl:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>So sánh mô hình trên backtest</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Mô hình</TableHead>
                        <TableHead className="text-right">WAPE</TableHead>
                        <TableHead className="text-right">WAPE bỏ Black Friday</TableHead>
                        <TableHead className="text-right">Thiên lệch</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {MODEL_ORDER.map((model) => {
                        const row = data.metrics.find((item) => item.model === model)
                        const used = model === data.chosen_model
                        return (
                          <TableRow key={model}>
                            <TableCell className="font-medium">
                              {MODEL_LABEL[model]}
                              {used ? <Badge variant="secondary" className="ml-2">đang dùng</Badge> : null}
                              {model === 'naive' ? <Badge variant="outline" className="ml-2">baseline</Badge> : null}
                              {model === data.best_model && data.best_model !== data.chosen_model ? (
                                <Badge variant="outline" className="ml-2">WAPE thấp nhất</Badge>
                              ) : null}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">{ratio(row?.wape)}</TableCell>
                            <TableCell className="text-right tabular-nums">{ratio(row?.wape_ex_event)}</TableCell>
                            <TableCell className="text-right tabular-nums">{ratio(row?.bias)}</TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                  <p className="mt-3 text-xs text-muted-foreground">{data.note}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Đánh đổi thiếu hàng và dư hàng</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Hệ số đệm của mỗi tháng chỉ học từ các tháng khác (leave-one-out), nên đây là tỷ lệ đo được trên dữ
                    liệu, không phải cam kết của phân vị.
                  </p>
                </CardHeader>
                <CardContent>
                  <TradeoffChart rows={data.tradeoff} />
                </CardContent>
              </Card>
            </div>
          </>
        ) : null}
      </QueryState>

      <Card>
        <CardHeader>
          <CardTitle>Độ chính xác theo mức tổng hợp</CardTitle>
          <p className="text-xs text-muted-foreground">
            Cùng một phương pháp, mức chi tiết càng cao thì sai số càng lớn. Báo cáo song song có và không có tháng
            Black Friday.
          </p>
        </CardHeader>
        <CardContent>
          <QueryState loading={accuracy.isLoading} error={accuracy.error}>
            {accuracy.data ? (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Mức tổng hợp</TableHead>
                      {MODEL_ORDER.map((model) => (
                        <TableHead key={model} className="text-right">
                          {MODEL_LABEL[model]}
                          {model === 'naive' ? ' (baseline)' : ''}
                        </TableHead>
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
                <p className="mt-3 text-xs text-muted-foreground">
                  WAPE gộp qua {accuracy.data.test_window.n_months} tháng kiểm tra ({accuracy.data.test_window.first} →{' '}
                  {accuracy.data.test_window.last}). Trong ngoặc là WAPE khi bỏ Black Friday 2017 và tháng sau.
                </p>
              </>
            ) : null}
          </QueryState>
        </CardContent>
      </Card>

      <WhatIfPanel selection={selection} scopeLabel={scopeLabel} applied={whatIf} onApply={setWhatIf} />
    </section>
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
            name="Lượng nhập đề xuất"
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

function TradeoffChart({ rows }: { rows: { service: number; stockout_rate: number | null; overstock_pct: number | null }[] }) {
  const chartRows = rows.map((row) => ({
    label: `${Math.round(row.service * 100)}%`,
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
          <Tooltip formatter={(value: unknown) => `${Number(value).toFixed(1)}%`} />
          <Legend />
          <Line type="monotone" dataKey="stockout" name="Tỷ lệ tháng thiếu hàng" stroke="#ff808b" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          <Line type="monotone" dataKey="overstock" name="Dư hàng trung bình" stroke={chartSales} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function ConclusionCard({ data, scopeLabel, whatIf }: { data: DssForecast; scopeLabel: string; whatIf: DssWhatIf | undefined }) {
  const unit = metricUnit[data.metric]
  const chosen = data.metrics.find((row) => row.model === data.chosen_model)
  const naive = data.metrics.find((row) => row.model === 'naive')
  const tradeoff = data.tradeoff.find((row) => Math.abs(row.service - data.service) < 1e-9)
  const service = Math.round(data.service * 100)
  const buffer = `${data.order.buffer_pct >= 0 ? '+' : ''}${data.order.buffer_pct.toFixed(1)}%`

  const base = whatIf?.promo.scenarios.find((row) => row.realization === 1)
  const flat = whatIf?.promo.scenarios.find((row) => row.realization === 0)
  const percent = (value: number) => `${Math.round(value * 100)}%`

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <CardTitle>Kết luận cho người quyết định · {scopeLabel}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          <li>
            <strong>Nhập hàng:</strong> tháng {data.next.month} dự báo bán khoảng {formatMetric(data.metric, data.next.forecast)}{' '}
            {unit}. Nên nhập khoảng {formatMetric(data.metric, data.order.quantity)} {unit} (đệm {buffer}, mức phục vụ {service}%).
            {tradeoff?.stockout_rate != null && tradeoff.overstock_pct != null
              ? ` Mô phỏng trên quá khứ, mức này vẫn thiếu hàng ở ${ratio(tradeoff.stockout_rate)} số tháng và dư trung bình ${tradeoff.overstock_pct.toFixed(1)}%.`
              : ''}
          </li>
          <li>
            <strong>Độ tin cậy:</strong> sai số backtest {ratio(chosen?.wape)} trên {chosen?.n ?? 0} tháng (bỏ Black Friday:{' '}
            {ratio(chosen?.wape_ex_event)}). Baseline "bằng tháng trước": {ratio(naive?.wape)} (bỏ Black Friday:{' '}
            {ratio(naive?.wape_ex_event)}). {baselineVerdict(data.chosen_model, chosen?.wape, naive?.wape)}
          </li>
          {whatIf && base && flat ? (
            <li>
              <strong>Khuyến mãi</strong> (giả định cầu tăng {percent(whatIf.inputs.uplift)}, giảm giá {percent(whatIf.inputs.discount)}, biên{' '}
              {percent(whatIf.inputs.margin)}):{' '}
              {whatIf.breakeven_uplift == null
                ? 'giảm giá không thấp hơn biên lợi nhuận nên mỗi món bán ra đều lỗ.'
                : `hòa vốn khi cầu tăng ít nhất ${percent(whatIf.breakeven_uplift)}. Nếu đạt đúng giả định, lợi nhuận ${signedPct(base.profit_change_pct)} so với không khuyến mãi; nếu cầu không tăng, ${signedPct(flat.profit_change_pct)}.`}
            </li>
          ) : null}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Dự báo dựa trên {data.history.length} tháng lịch sử. Phần khuyến mãi là kịch bản theo giả định bạn nhập, không suy ra từ dữ liệu;
          nó tính theo số món bất kể đo lường đang chọn.
        </p>
      </CardContent>
    </Card>
  )
}
