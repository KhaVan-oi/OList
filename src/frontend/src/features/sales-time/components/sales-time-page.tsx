import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TrendingUpIcon, BarChart2Icon, GridIcon } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Button } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { FilterSelect, filterBarClass } from '../../../components/ui/filter-select.tsx'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../../components/ui/table.tsx'
import type { Row } from '../../../types/api.ts'
import {
  DICE_GROUP_RANK,
  diceGroupOf,
  endpointFor,
  KPI_OPTIONS,
  kpiKeyOf,
  matrixEndpointFor,
  monthsOfQuarter,
  operationOf,
  rowLabel,
  timeLevelOf,
  type DiceGroup,
  type KpiValue,
  type TimeLevel,
} from '../depth.ts'
import { getSalesTime } from '../services/salesTimeApi.ts'
import { TimeChart } from './time-chart.tsx'
import { money, count, pct } from '../../../lib/format.ts'

// ─── Tên tiếng Việt cho các tháng ───────────────────────────────────────────
const MONTH_VI = [
  'Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4',
  'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8',
  'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12',
]

const YEARS = ['2016', '2017', '2018']

type Col = { key: string; label: string }

// ─── Tiêu đề cột bảng mặc định (đủ 3 measure, bảng sẽ lọc theo measure đang chọn) ──
const MEASURE_COLS: Col[] = [
  { key: 'product_sales', label: 'Doanh thu (R$)' },
  { key: 'freight_value', label: 'Phí vận chuyển (R$)' },
  { key: 'order_item_count', label: 'Số lượng' },
]

function growthCols(prefix: 'yoy' | 'qoq' | 'mom'): Col[] {
  // Năm và quý: backend so CÙNG KỲ (chỉ các tháng có ở cả hai kỳ), xem growth.py
  const suffix = prefix === 'mom' ? '' : ' cùng kỳ'
  return [
    { key: `${prefix}_product_sales_pct`, label: `Tăng trưởng DT${suffix} (%)` },
    { key: `${prefix}_freight_value_pct`, label: `Tăng trưởng Phí${suffix} (%)` },
    { key: `${prefix}_order_item_count_pct`, label: `Tăng trưởng SL${suffix} (%)` },
  ]
}

/** Số tháng có dữ liệu của kỳ và số tháng dùng để so cùng kỳ */
const COVERAGE_COLS: Col[] = [
  { key: 'months_with_data', label: 'Số tháng có dữ liệu' },
  { key: 'months_compared', label: 'Số tháng so cùng kỳ' },
]

const TIME_COLS: Record<TimeLevel, Col[]> = {
  year: [{ key: 'year', label: 'Năm' }, ...MEASURE_COLS, ...growthCols('yoy'), ...COVERAGE_COLS],
  quarter: [
    { key: 'year', label: 'Năm' },
    { key: 'quarter', label: 'Quý' },
    ...MEASURE_COLS,
    ...growthCols('qoq'),
    ...COVERAGE_COLS,
  ],
  month: [{ key: 'year', label: 'Năm' }, { key: 'month', label: 'Tháng' }, ...MEASURE_COLS, ...growthCols('mom')],
  day: [
    { key: 'full_date', label: 'Ngày' },
    ...MEASURE_COLS,
    { key: 'is_weekend', label: 'Loại ngày' },
  ],
}

const DICE_COLS: Record<DiceGroup, Col[]> = {
  year: [{ key: 'year', label: 'Năm' }, ...MEASURE_COLS],
  quarter: [{ key: 'year', label: 'Năm' }, { key: 'quarter', label: 'Quý' }, ...MEASURE_COLS],
  month: [
    { key: 'year', label: 'Năm' },
    { key: 'quarter', label: 'Quý' },
    { key: 'month', label: 'Tháng' },
    ...MEASURE_COLS,
  ],
  day: [{ key: 'full_date', label: 'Ngày' }, ...MEASURE_COLS, { key: 'is_weekend', label: 'Loại ngày' }],
}

// ─── Format giá trị ô bảng ───────────────────────────────────────────────────
function fmtCell(key: string, value: Row[string]): string {
  if (value == null) return '—'
  if (key === 'is_weekend') return value === true ? '🏖 Cuối tuần' : '💼 Ngày thường'
  if (key === 'quarter') return `Q${value}`
  if (key === 'month' && typeof value === 'number') return MONTH_VI[value - 1] ?? String(value)
  if (key.endsWith('_pct') && typeof value === 'number') return pct(value)
  if (key === 'product_sales' || key === 'freight_value') return money(typeof value === 'number' ? value : Number(value))
  if (key === 'order_item_count') return count(typeof value === 'number' ? value : Number(value))
  if (key === 'full_date') return String(value).slice(0, 10)
  return String(value)
}

function pctClass(key: string, value: Row[string]): string {
  if (!key.endsWith('_pct') || value == null) return ''
  return Number(value) > 0 ? 'text-emerald-600' : Number(value) < 0 ? 'text-rose-500' : ''
}

/** Cột này thuộc measure nào: sales | freight | count; cột thời gian trả về null */
function measureOfCol(key: string): KpiValue | null {
  if (key.includes('product_sales')) return 'sales'
  if (key.includes('freight')) return 'freight'
  if (key.includes('order_item_count')) return 'count'
  return null
}

// ─── Bảng Ma trận (Tháng × Năm) của measure đang chọn ────────────────────────
function MatrixTable({
  rows,
  activeKpi,
  years,
  months,
}: {
  rows: Row[]
  activeKpi: KpiValue
  years: string[]
  months: number[]
}) {
  const option = KPI_OPTIONS.find((k) => k.value === activeKpi) ?? KPI_OPTIONS[0]
  const cell = new Map<string, Row[string]>()
  for (const r of rows) cell.set(`${r.year}-${r.month}`, r[option.key])
  const fmtVal = (v: Row[string] | undefined) => {
    if (v == null) return <span className="text-muted-foreground">—</span>
    return <>{activeKpi === 'count' ? count(Number(v)) : money(Number(v))}</>
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tháng</TableHead>
            {years.map((y) => (
              <TableHead key={y} className="text-right">{y}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {months.map((m) => (
            <TableRow key={m}>
              <TableCell className="font-medium">{MONTH_VI[m - 1]}</TableCell>
              {years.map((y) => (
                <TableCell key={y} className="text-right tabular-nums">{fmtVal(cell.get(`${y}-${m}`))}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// ─── Bảng dữ liệu mặc định ──────────────────────────────────────────────────
function DataTable({ rows, cols, activeKpi }: { rows: Row[]; cols: Col[]; activeKpi: KpiValue }) {
  // Cột thời gian luôn hiện; cột measure chỉ hiện khi khớp measure đang chọn
  const displayCols = cols.filter((c) => {
    const kind = measureOfCol(c.key)
    return kind == null || kind === activeKpi
  })

  if (!rows.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
        <span className="text-2xl">📭</span>
        <span>Không có dữ liệu cho bộ lọc đã chọn</span>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {displayCols.map((c) => (
            <TableHead key={c.key}>{c.label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => (
          <TableRow
            key={i}
            className={row.is_weekend === true ? 'bg-violet-50/50 dark:bg-violet-950/20' : ''}
          >
            {displayCols.map((c) => (
              <TableCell key={c.key} className={pctClass(c.key, row[c.key])}>
                {fmtCell(c.key, row[c.key])}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

const WEEKEND_OPTIONS = (
  <>
    <option value="">Mọi ngày</option>
    <option value="0">Ngày thường</option>
    <option value="1">Cuối tuần</option>
  </>
)

const QUARTER_OPTIONS = (
  <>
    <option value="1">Q1</option>
    <option value="2">Q2</option>
    <option value="3">Q3</option>
    <option value="4">Q4</option>
  </>
)

function MonthOptions({ quarter }: { quarter: string }) {
  return (
    <>
      <option value="">Cả quý</option>
      {monthsOfQuarter(quarter).map((m) => (
        <option key={m} value={String(m)}>{MONTH_VI[m - 1]}</option>
      ))}
    </>
  )
}

// ─── Component chính ─────────────────────────────────────────────────────────
export function SalesTimePage() {
  const [params, setParams] = useSearchParams()
  const [tableMode, setTableMode] = useState<'default' | 'matrix'>('default')

  const op = operationOf(params)
  const level = timeLevelOf(params)
  const activeKpi: KpiValue = (params.get('kpi') as KpiValue) ?? 'sales'
  const isDice = op === 'dice'
  const isPivot = op === 'pivot'

  // Bộ lọc Dice
  const yearFrom = params.get('year_from') ?? '2016'
  const yearTo = params.get('year_to') ?? '2018'
  const diceGroup = diceGroupOf(params)
  const diceRank = DICE_GROUP_RANK[diceGroup]

  // Bộ lọc dùng chung tên trong URL: Một kỳ (year/quarter/month/weekend) và Dice (quarter/month/weekend)
  const year = params.get('year') ?? ''
  const quarter = params.get('quarter') ?? ''
  const month = params.get('month') ?? ''
  const weekend = params.get('weekend') ?? ''

  const path = endpointFor(params)
  const query = useQuery({ queryKey: ['sales-time', path], queryFn: () => getSalesTime(path) })
  const rows = (query.data?.data ?? []).map((row) => ({ ...row, label: rowLabel(row, op) }))

  // Ma trận Tháng × Năm: cùng bộ lọc với chế độ đang xem, chỉ tải khi mở ma trận
  const matrixPath = matrixEndpointFor(params)
  const matrix = useQuery({
    queryKey: ['sales-time', matrixPath],
    queryFn: () => getSalesTime(matrixPath),
    enabled: tableMode === 'matrix' && !isPivot,
  })
  const matrixYears = isDice
    ? YEARS.filter((y) => y >= yearFrom && y <= yearTo)
    : year
      ? [year]
      : YEARS
  const matrixMonths = month ? [Number(month)] : monthsOfQuarter(quarter)

  // Pivot: API trả mỗi tháng một dòng {month, val_2016, val_2017, val_2018}. Đổi sang dạng dài
  // {year, month, <measure>} để dùng lại MatrixTable (cùng định dạng tiền / số lượng với bảng Ma trận).
  const kpiField = kpiKeyOf(activeKpi)
  const pivotRows: Row[] = isPivot
    ? (query.data?.data ?? []).flatMap((r) =>
        YEARS.map((y) => ({ year: y, month: r.month, [kpiField]: r[`val_${y}`] ?? null })),
      )
    : []

  const tableCols = isDice ? DICE_COLS[diceGroup] : TIME_COLS[level]

  // Có thể drill vào không (một kỳ: năm → quý → tháng → ngày)
  const canDrill = op === 'timeanalysis' && level !== 'day'

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next)
  }

  // Nhấn cột = chọn đúng giá trị tương ứng ở bộ lọc cấp đó
  function handleDrillFromChart(row: Row) {
    if (op !== 'timeanalysis') return
    if (level === 'year' && row.year != null) update({ year: String(row.year), quarter: null, month: null, weekend: null })
    else if (level === 'quarter' && row.quarter != null) update({ quarter: String(row.quarter), month: null, weekend: null })
    else if (level === 'month' && row.month != null) update({ month: String(row.month), weekend: null })
  }

  // Xem cấp trên = bỏ lựa chọn sâu nhất
  function handleClimbUp() {
    if (month) update({ month: null, weekend: null })
    else if (quarter) update({ quarter: null })
    else if (year) update({ year: null })
  }

  // Chuyển sang Dice (nhiều năm)
  function switchToDice() {
    setParams(new URLSearchParams({ op: 'dice', year_from: '2016', year_to: '2018', group_by: 'year', kpi: activeKpi }))
  }

  // Trở về Phân tích một kỳ
  function switchToTimeanalysis() {
    setParams(new URLSearchParams({ op: 'timeanalysis', kpi: activeKpi }))
  }

  // Thay đổi KPI (đồng bộ biểu đồ + bảng + ma trận)
  function setKpi(kpi: string) {
    if (isPivot) {
      setParams(new URLSearchParams({ op: 'pivot', kpi, type: params.get('type') ?? 'value' }))
      return
    }
    update({ kpi })
  }

  // Đổi Nhóm theo: ẩn và reset các bộ lọc không còn thuộc cấp mới
  function changeDiceGroup(group: DiceGroup) {
    const rank = DICE_GROUP_RANK[group]
    update({
      group_by: group,
      quarter: rank >= 1 ? quarter : null,
      month: rank >= 2 ? month : null,
      weekend: rank >= 3 ? weekend : null,
    })
  }

  function changeDiceQuarter(value: string) {
    const stillValid = month && (!value || monthsOfQuarter(value).includes(Number(month)))
    update({ quarter: value, month: stillValid ? month : null })
  }

  const levelLabel: Record<TimeLevel, string> = {
    year: 'Năm',
    quarter: 'Quý',
    month: 'Tháng',
    day: 'Ngày',
  }

  const canClimbUp = op === 'timeanalysis' && Boolean(year)
  const kpiLabel = KPI_OPTIONS.find((k) => k.value === activeKpi)?.label ?? ''

  const cardTitle = isDice
    ? `Phân tích nhiều năm — nhóm theo ${levelLabel[diceGroup].toLowerCase()}`
    : isPivot
      ? 'Ma trận Tháng × Năm'
      : `Phân tích thời gian — cấp ${levelLabel[level]}`

  return (
    <section className="space-y-4">
      <PageHeading
        title="Thời gian"
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            {/* KPI Measure selector */}
            <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm">
              {KPI_OPTIONS.map((kpi) => (
                <button
                  key={kpi.value}
                  type="button"
                  onClick={() => setKpi(kpi.value)}
                  className={[
                    'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                    activeKpi === kpi.value
                      ? 'bg-primary text-primary-foreground shadow'
                      : 'text-muted-foreground hover:text-foreground',
                  ].join(' ')}
                >
                  {kpi.label}
                </button>
              ))}
            </div>

            {/* Nút Nhiều năm / Một kỳ — nằm hàng trên, tách khỏi thanh bộ lọc */}
            <Button
              type="button"
              variant={isDice ? 'default' : 'outline'}
              size="sm"
              onClick={isDice ? switchToTimeanalysis : switchToDice}
            >
              <BarChart2Icon className="size-4" />
              {isDice ? 'Một kỳ' : 'Nhiều năm'}
            </Button>
          </div>
        }
      />

      {/* Thanh bộ lọc — hàng riêng, tự xuống dòng khi hẹp */}
      {!isPivot ? (
        <div className="flex justify-end">
          {!isDice ? (
            <div className={filterBarClass}>
              <TrendingUpIcon className="ml-1 size-4 text-muted-foreground" />

              {/* Bộ lọc 1: Toàn kỳ / năm */}
              <FilterSelect
                id="time-year"
                label="Năm"
                minWidth="7rem"
                value={year}
                onChange={(v) => update({ year: v, quarter: null, month: null, weekend: null })}
              >
                <option value="">Toàn kỳ</option>
                {YEARS.map((y) => (
                  <option key={y} value={y}>{`Năm ${y}`}</option>
                ))}
              </FilterSelect>

              {/* Bộ lọc 2: Cả năm / quý (chỉ khi đã chọn năm) */}
              {year ? (
                <FilterSelect
                  id="time-quarter"
                  label="Quý"
                  value={quarter}
                  onChange={(v) => update({ quarter: v, month: null, weekend: null })}
                >
                  <option value="">Cả năm</option>
                  {QUARTER_OPTIONS}
                </FilterSelect>
              ) : null}

              {/* Bộ lọc 3: Cả quý / tháng (chỉ khi đã chọn quý) */}
              {year && quarter ? (
                <FilterSelect
                  id="time-month"
                  label="Tháng"
                  minWidth="7rem"
                  value={month}
                  onChange={(v) => update({ month: v, weekend: null })}
                >
                  <MonthOptions quarter={quarter} />
                </FilterSelect>
              ) : null}

              {/* Bộ lọc 4: Mọi ngày / ngày thường / cuối tuần (chỉ khi đã chọn tháng) */}
              {year && quarter && month ? (
                <FilterSelect
                  id="time-weekend"
                  label="Loại ngày"
                  minWidth="8rem"
                  value={weekend}
                  onChange={(v) => update({ weekend: v })}
                >
                  {WEEKEND_OPTIONS}
                </FilterSelect>
              ) : null}
            </div>
          ) : (
            <div className={filterBarClass}>
              <BarChart2Icon className="ml-1 size-4 text-muted-foreground" />
              <FilterSelect
                id="dice-year-from"
                label="Từ năm nào"
                minWidth="6rem"
                value={yearFrom}
                onChange={(v) => update({ year_from: v, year_to: Number(v) > Number(yearTo) ? v : yearTo })}
              >
                {YEARS.map((y) => (
                  <option key={y} value={y}>{`Từ ${y}`}</option>
                ))}
              </FilterSelect>
              <FilterSelect
                id="dice-year-to"
                label="Đến năm nào"
                minWidth="6rem"
                value={yearTo}
                onChange={(v) => update({ year_to: v, year_from: Number(v) < Number(yearFrom) ? v : yearFrom })}
              >
                {YEARS.map((y) => (
                  <option key={y} value={y}>{`Đến ${y}`}</option>
                ))}
              </FilterSelect>

              {diceRank >= 1 ? (
                <FilterSelect id="dice-quarter" label="Quý" value={quarter} onChange={changeDiceQuarter}>
                  <option value="">Cả năm</option>
                  {QUARTER_OPTIONS}
                </FilterSelect>
              ) : null}

              {diceRank >= 2 ? (
                <FilterSelect
                  id="dice-month"
                  label="Tháng"
                  minWidth="7rem"
                  value={month}
                  onChange={(v) => update({ month: v })}
                >
                  <MonthOptions quarter={quarter} />
                </FilterSelect>
              ) : null}

              {diceRank >= 3 ? (
                <FilterSelect
                  id="dice-weekend"
                  label="Ngày"
                  minWidth="8rem"
                  value={weekend}
                  onChange={(v) => update({ weekend: v })}
                >
                  {WEEKEND_OPTIONS}
                </FilterSelect>
              ) : null}

              {/* Nhóm theo luôn nằm cuối, bên phải */}
              <FilterSelect
                id="dice-group-by"
                label="Nhóm theo"
                minWidth="7.5rem"
                value={diceGroup}
                onChange={(v) => changeDiceGroup(v as DiceGroup)}
              >
                <option value="year">Nhóm theo: Năm</option>
                <option value="quarter">Nhóm theo: Quý</option>
                <option value="month">Nhóm theo: Tháng</option>
                <option value="day">Nhóm theo: Ngày</option>
              </FilterSelect>
            </div>
          )}
        </div>
      ) : null}

      {/* Card biểu đồ */}
      <Card>
        <CardHeader>
          <CardTitle>{cardTitle}</CardTitle>
          {canClimbUp ? (
            <CardAction>
              <Button type="button" variant="outline" size="sm" onClick={handleClimbUp}>
                ↑ Xem cấp trên
              </Button>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent>
          <QueryState loading={query.isLoading} error={query.error}>
            <TimeChart
              rows={rows}
              operation={op}
              activeKpi={activeKpi}
              canDrill={canDrill}
              onDrill={handleDrillFromChart}
            />
          </QueryState>
        </CardContent>
      </Card>

      {/* Card bảng dữ liệu */}
      <Card>
        <CardHeader>
          <CardTitle>
            {tableMode === 'matrix' || isPivot ? `Ma trận Tháng × Năm — ${kpiLabel}` : 'Dữ liệu chi tiết'}
          </CardTitle>
          {/* Chuyển đổi chế độ bảng: Mặc định / Ma trận (giữ nguyên bộ lọc). Pivot vốn là ma trận nên không cần. */}
          {!isPivot && (
          <CardAction>
            <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-muted p-1">
              <button
                type="button"
                onClick={() => setTableMode('default')}
                className={[
                  'rounded-lg px-3 py-1 text-xs font-semibold transition-colors',
                  tableMode === 'default'
                    ? 'bg-background text-foreground shadow'
                    : 'text-muted-foreground hover:text-foreground',
                ].join(' ')}
              >
                Mặc định
              </button>
              <button
                type="button"
                onClick={() => setTableMode('matrix')}
                className={[
                  'inline-flex items-center gap-1 rounded-lg px-3 py-1 text-xs font-semibold transition-colors',
                  tableMode === 'matrix'
                    ? 'bg-background text-foreground shadow'
                    : 'text-muted-foreground hover:text-foreground',
                ].join(' ')}
              >
                <GridIcon className="size-3" />
                Ma trận
              </button>
            </div>
          </CardAction>
          )}
        </CardHeader>
        <CardContent>
          {isPivot ? (
            <QueryState loading={query.isLoading} error={query.error}>
              <MatrixTable rows={pivotRows} activeKpi={activeKpi} years={YEARS} months={monthsOfQuarter('')} />
            </QueryState>
          ) : tableMode === 'matrix' ? (
            <QueryState loading={matrix.isLoading} error={matrix.error}>
              <MatrixTable
                rows={matrix.data?.data ?? []}
                activeKpi={activeKpi}
                years={matrixYears}
                months={matrixMonths}
              />
            </QueryState>
          ) : (
            <QueryState loading={query.isLoading} error={query.error}>
              <DataTable rows={rows} cols={tableCols} activeKpi={activeKpi} />
              {!isDice && (level === 'year' || level === 'quarter') ? (
                <p className="mt-3 text-xs text-muted-foreground">
                  Tăng trưởng {level === 'year' ? 'năm' : 'quý'} chỉ so <strong>cùng kỳ</strong>. Cột doanh thu vẫn là tổng đầy đủ của kỳ.
                </p>
              ) : null}
            </QueryState>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
