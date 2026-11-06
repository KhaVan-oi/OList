import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart2Icon, GridIcon, UsersIcon } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Button } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { FilterSelect, filterBarClass } from '../../../components/ui/filter-select.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table.tsx'
import { count, money, pct } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import { getOverview } from '../../overview/services/overviewApi.ts'
import {
  allCustomerStates,
  CUSTOMER_KPIS,
  DICE_DEFAULT_STATES,
  DIM_OPTIONS,
  diceStatesOf,
  dimOf,
  drilldownQuery,
  drillLevelOf,
  formatKpiValue,
  GROUP_OPTIONS,
  groupOf,
  kpiOf,
  kpiOption,
  modeOf,
  ORDER_STATUSES,
  stateOf,
  statusOf,
  type CustomerKpi,
  type Dim,
} from '../depth.ts'
import {
  getCustomerDice,
  getCustomerDrilldown,
  getCustomerMatrix,
  getCustomerRanking,
} from '../services/customerPaymentApi.ts'
import { CustomerChart, CustomerDiceChart } from './customer-chart.tsx'

const YEARS = ['2016', '2017', '2018']

const FIRST_COL: Record<Dim, [string, string]> = {
  customer: ['Nhóm khách', 'Bậc tần suất'],
  geo: ['Bang', 'Thành phố'],
  status: ['Trạng thái đơn', 'Bang'],
}

const SCOPE_TITLE: Record<Dim, [string, string]> = {
  customer: ['Nhóm khách (mua một lần / mua lại)', 'Bậc tần suất'],
  geo: ['Khách theo bang', 'Top 15 thành phố'],
  status: ['Đơn theo trạng thái', 'Đơn theo bang'],
}

const money2 = (n: number) => money(n)
const count0 = (n: number) => count(n)

export function CustomerPaymentPage() {
  const [params, setParams] = useSearchParams()
  const [tableMode, setTableMode] = useState<'default' | 'matrix'>('default')

  const mode = modeOf(params)
  const isDice = mode === 'dice'
  const dim = dimOf(params)
  const kpi = kpiOf(params)
  const group = groupOf(params)
  const state = stateOf(params)
  const status = statusOf(params)
  const level = drillLevelOf(params)
  const diceStates = diceStatesOf(params)
  const yearFrom = params.get('year_from') ?? '2017'
  const yearTo = params.get('year_to') ?? '2018'
  const option = kpiOption(kpi)

  const overview = useQuery({ queryKey: ['overview'], queryFn: getOverview })
  const customers = overview.data?.customers
  const total = customers ? customers.one_time + customers.repeat_buyers : 0
  const repeatRate = total ? (customers!.repeat_buyers / total) * 100 : null

  const drillQs = drilldownQuery(params)
  const drill = useQuery({
    queryKey: ['customer-payment', 'drilldown', drillQs],
    queryFn: () => getCustomerDrilldown(drillQs),
    enabled: !isDice,
  })
  const dice = useQuery({
    queryKey: ['customer-payment', 'dice', diceStates.join(','), yearFrom, yearTo],
    queryFn: () => getCustomerDice(diceStates, yearFrom, yearTo),
    enabled: isDice,
  })
  // Ma trận Bang × Năm: giữ lọc bang đang chọn ở chiều Địa lý
  const matrixStates = dim === 'geo' && state ? [state] : []
  const matrix = useQuery({
    queryKey: ['customer-payment', 'matrix', matrixStates.join(',')],
    queryFn: () => getCustomerMatrix(matrixStates),
    enabled: tableMode === 'matrix' && !isDice,
  })
  const rankStates = isDice ? diceStates : []
  const ranking = useQuery({
    queryKey: ['customer-payment', 'ranking', rankStates.join(',')],
    queryFn: () => getCustomerRanking(rankStates),
  })

  const drillRows = drill.data?.data ?? []
  const diceRows = dice.data?.data ?? []
  const active = isDice ? dice : drill

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next)
  }

  // Nhấn cột = chọn đúng giá trị ở bộ lọc cấp đó
  function handleDrill(row: Row) {
    const key = String(row.key ?? '')
    if (!key || level > 0) return
    if (dim === 'customer') update({ group: key })
    else if (dim === 'geo') update({ state: key })
    else update({ status: key })
  }

  function handleClimbUp() {
    update({ group: null, state: null, status: null })
  }

  function changeDim(next: Dim) {
    setParams(new URLSearchParams({ dim: next, kpi }))
  }

  function switchToDice() {
    setParams(
      new URLSearchParams({
        mode: 'dice',
        kpi,
        states: DICE_DEFAULT_STATES.join(','),
        year_from: '2017',
        year_to: '2018',
      }),
    )
  }

  function switchToDrill() {
    setParams(new URLSearchParams({ kpi }))
  }

  function toggleDiceState(code: string) {
    const next = diceStates.includes(code) ? diceStates.filter((item) => item !== code) : [...diceStates, code]
    if (next.length === 0) return
    update({ states: next.join(',') })
  }

  const canDrill = !isDice && level === 0
  const canClimbUp = !isDice && level > 0
  const [rootTitle, childTitle] = SCOPE_TITLE[dim]
  const chartTitle = isDice
    ? 'Khối — bang × năm × khách mua lại'
    : `${dimLabel(dim)} — ${level === 0 ? rootTitle : childTitle}`
  const scopeLabel = scopeName(dim, group, state, status)

  return (
    <section className="space-y-4">
      <PageHeading
        title="Khách hàng"
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            {/* Measure selector: đồng bộ biểu đồ, bảng và ma trận */}
            <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm">
              {CUSTOMER_KPIS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => update({ kpi: item.value })}
                  className={[
                    'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                    kpi === item.value
                      ? 'bg-primary text-primary-foreground shadow'
                      : 'text-muted-foreground hover:text-foreground',
                  ].join(' ')}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <Button
              type="button"
              variant={isDice ? 'default' : 'outline'}
              size="sm"
              onClick={isDice ? switchToDrill : switchToDice}
            >
              <BarChart2Icon className="size-4" />
              {isDice ? 'Drill-down' : 'Dice'}
            </Button>
          </div>
        }
      />

      <QueryState loading={overview.isLoading} error={overview.error}>
        {customers && (
          <div className="grid gap-4 md:grid-cols-3">
            <Stat label="Khách" value={count(total)} detail={`${count(customers.one_time)} mua một đơn`} />
            <Stat label="Mua lại" value={pct(repeatRate)} detail={`${count(customers.repeat_buyers)} khách`} />
            <Stat label="Chi trên 1.000 R$" value={count(customers.vip)} detail="Theo tổng thanh toán" />
          </div>
        )}
      </QueryState>

      {/* Thanh bộ lọc — hàng riêng, tự xuống dòng khi hẹp */}
      <div className="flex justify-end">
        {!isDice ? (
          <div className={filterBarClass}>
            <UsersIcon className="ml-1 size-4 text-muted-foreground" />
            <FilterSelect id="cp-dim" label="Chiều" minWidth="8.5rem" value={dim} onChange={(v) => changeDim(v as Dim)}>
              {DIM_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{`${item.label}`}</option>
              ))}
            </FilterSelect>

            {dim === 'customer' ? (
              <FilterSelect
                id="cp-group"
                label="Nhóm khách"
                minWidth="8rem"
                value={group}
                onChange={(v) => update({ group: v })}
              >
                <option value="">Toàn bộ khách</option>
                {GROUP_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </FilterSelect>
            ) : null}

            {dim === 'geo' ? (
              <FilterSelect
                id="cp-state"
                label="Bang"
                minWidth="7rem"
                value={state}
                onChange={(v) => update({ state: v })}
              >
                <option value="">Toàn quốc</option>
                {allCustomerStates.map((code) => (
                  <option key={code} value={code}>{`Bang ${code}`}</option>
                ))}
              </FilterSelect>
            ) : null}

            {dim === 'status' ? (
              <FilterSelect
                id="cp-status"
                label="Trạng thái đơn"
                minWidth="8rem"
                value={status}
                onChange={(v) => update({ status: v })}
              >
                <option value="">Mọi trạng thái</option>
                {ORDER_STATUSES.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </FilterSelect>
            ) : null}
          </div>
        ) : (
          <div className={filterBarClass}>
            <BarChart2Icon className="ml-1 size-4 text-muted-foreground" />
            <FilterSelect
              id="cp-year-from"
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
              id="cp-year-to"
              label="Đến năm nào"
              minWidth="6rem"
              value={yearTo}
              onChange={(v) => update({ year_to: v, year_from: Number(v) < Number(yearFrom) ? v : yearFrom })}
            >
              {YEARS.map((y) => (
                <option key={y} value={y}>{`Đến ${y}`}</option>
              ))}
            </FilterSelect>
            <span className="h-5 w-px bg-border" aria-hidden />
            <StatePicker selected={diceStates} onToggle={toggleDiceState} />
          </div>
        )}
      </div>

      {/* Biểu đồ */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>{chartTitle}</CardTitle>
            {!isDice && scopeLabel ? (
              <p className="mt-1 text-xs text-muted-foreground">{scopeLabel}</p>
            ) : null}
          </div>
          {canClimbUp ? (
            <CardAction>
              <Button type="button" variant="outline" size="sm" onClick={handleClimbUp}>
                ↑ Xem cấp trên
              </Button>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-2">
          <QueryState loading={active.isLoading} error={active.error}>
            {isDice ? (
              <CustomerDiceChart rows={diceRows} kpi={kpi} />
            ) : (
              <CustomerChart rows={drillRows} kpi={kpi} canDrill={canDrill} onDrill={handleDrill} />
            )}
          </QueryState>
          {active.data?.note ? <p className="text-xs text-muted-foreground">{active.data.note}</p> : null}
        </CardContent>
      </Card>

      {/* Bảng dữ liệu */}
      <Card>
        <CardHeader>
          <CardTitle>
            {tableMode === 'matrix' ? `Ma trận Bang × Năm — ${option.label}` : 'Dữ liệu chi tiết'}
          </CardTitle>
          <CardAction>
            <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-muted p-1">
              <TableModeButton active={tableMode === 'default'} onClick={() => setTableMode('default')}>
                Mặc định
              </TableModeButton>
              <TableModeButton active={tableMode === 'matrix'} onClick={() => setTableMode('matrix')}>
                <GridIcon className="size-3" />
                Ma trận
              </TableModeButton>
            </div>
          </CardAction>
        </CardHeader>
        <CardContent>
          {tableMode === 'matrix' ? (
            isDice ? (
              <QueryState loading={dice.isLoading} error={dice.error}>
                <MatrixTable
                  rows={diceRows}
                  kpi={kpi}
                  states={diceStates}
                  years={YEARS.filter((y) => y >= yearFrom && y <= yearTo)}
                />
              </QueryState>
            ) : (
              <QueryState loading={matrix.isLoading} error={matrix.error}>
                <MatrixTable
                  rows={matrix.data?.data ?? []}
                  kpi={kpi}
                  states={matrixStates.length ? matrixStates : stateCodesIn(matrix.data?.data ?? [])}
                  years={YEARS}
                />
              </QueryState>
            )
          ) : isDice ? (
            <QueryState loading={dice.isLoading} error={dice.error}>
              <DiceTable rows={diceRows} kpi={kpi} />
            </QueryState>
          ) : (
            <QueryState loading={drill.isLoading} error={drill.error}>
              <DrillTable
                rows={drillRows}
                total={drill.data?.total}
                kpi={kpi}
                firstCol={FIRST_COL[dim][level]}
              />
            </QueryState>
          )}
        </CardContent>
      </Card>

      {/* Hạng chi tiêu (window function) */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Top 3 khách chi nhiều nhất theo bang</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
            </p>
          </div>
        </CardHeader>
        <CardContent>
          <QueryState loading={ranking.isLoading} error={ranking.error}>
            <RankingTable rows={ranking.data?.data ?? []} />
          </QueryState>
        </CardContent>
      </Card>
    </section>
  )
}

function dimLabel(dim: Dim) {
  return DIM_OPTIONS.find((item) => item.value === dim)?.label ?? ''
}

function scopeName(dim: Dim, group: string, state: string, status: string) {
  if (dim === 'customer' && group) return `Nhóm: ${GROUP_OPTIONS.find((g) => g.value === group)?.label}`
  if (dim === 'geo' && state) return `Bang ${state}`
  if (dim === 'status' && status) return `Trạng thái: ${status}`
  return ''
}

function stateCodesIn(rows: Row[]) {
  return [...new Set(rows.map((r) => String(r.customer_state)))]
}

function TableModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'inline-flex items-center gap-1 rounded-lg px-3 py-1 text-xs font-semibold transition-colors',
        active ? 'bg-background text-foreground shadow' : 'text-muted-foreground hover:text-foreground',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

/** Chọn nhiều bang cho Dice. Luôn giữ ít nhất một bang. */
function StatePicker({ selected, onToggle }: { selected: string[]; onToggle: (code: string) => void }) {
  return (
    <details className="relative">
      <summary className="flex h-8 cursor-pointer list-none items-center gap-1 rounded-lg px-3 text-sm select-none">
        {`Bang: ${selected.length > 4 ? `${selected.slice(0, 4).join(', ')}…` : selected.join(', ')} (${selected.length})`}
      </summary>
      <div className="absolute right-0 z-20 mt-1 grid w-64 grid-cols-5 gap-1 rounded-xl border border-border bg-card p-2 shadow-lg">
        {allCustomerStates.map((code) => (
          <label
            key={code}
            className={[
              'flex cursor-pointer items-center justify-center rounded-md border px-1 py-1 text-xs font-medium',
              selected.includes(code)
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border text-muted-foreground hover:text-foreground',
            ].join(' ')}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={selected.includes(code)}
              onChange={() => onToggle(code)}
            />
            {code}
          </label>
        ))}
      </div>
    </details>
  )
}

function DrillTable({
  rows,
  total,
  kpi,
  firstCol,
}: {
  rows: Row[]
  total?: Row
  kpi: CustomerKpi
  firstCol: string
}) {
  const option = kpiOption(kpi)
  if (!rows.length) return <p className="py-8 text-center text-sm text-muted-foreground">Không có dữ liệu.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{firstCol}</TableHead>
          <TableHead className="text-right">{option.label}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={String(row.key)}>
            <TableCell>{String(row.label ?? row.key)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatKpiValue(kpi, row[option.key], money2, count0)}
            </TableCell>
          </TableRow>
        ))}
        {total ? (
          <TableRow className="font-semibold">
            <TableCell>Tổng (đếm lại)</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatKpiValue(kpi, total[option.key], money2, count0)}
            </TableCell>
          </TableRow>
        ) : null}
      </TableBody>
    </Table>
  )
}

function DiceTable({ rows, kpi }: { rows: Row[]; kpi: CustomerKpi }) {
  const option = kpiOption(kpi)
  if (!rows.length) return <p className="py-8 text-center text-sm text-muted-foreground">Không có dữ liệu.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Bang</TableHead>
          <TableHead>Năm</TableHead>
          <TableHead className="text-right">{option.label}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.customer_state}-${row.year}`}>
            <TableCell>{String(row.customer_state)}</TableCell>
            <TableCell>{String(row.year)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatKpiValue(kpi, row[option.key], money2, count0)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

/** Hàng: bang · Cột: năm · Giá trị: measure đang chọn. Khách đếm riêng từng ô, không có dòng tổng. */
function MatrixTable({ rows, kpi, states, years }: { rows: Row[]; kpi: CustomerKpi; states: string[]; years: string[] }) {
  const option = kpiOption(kpi)
  const cell = new Map<string, Row[string]>()
  for (const r of rows) cell.set(`${r.customer_state}-${r.year}`, r[option.key])
  if (!states.length) return <p className="py-8 text-center text-sm text-muted-foreground">Không có dữ liệu.</p>
  return (
    <div className="space-y-2">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Bang</TableHead>
            {years.map((y) => (
              <TableHead key={y} className="text-right">{y}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {states.map((code) => (
            <TableRow key={code}>
              <TableCell className="font-medium">{code}</TableCell>
              {years.map((y) => (
                <TableCell key={y} className="text-right tabular-nums">
                  {formatKpiValue(kpi, cell.get(`${code}-${y}`), money2, count0)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function RankingTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <p className="py-8 text-center text-sm text-muted-foreground">Không có dữ liệu.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Bang</TableHead>
          <TableHead>Hạng</TableHead>
          <TableHead>Khách</TableHead>
          <TableHead className="text-right">Số đơn</TableHead>
          <TableHead className="text-right">Chi tiêu tại bang (R$)</TableHead>
          <TableHead className="text-right">Phân vị toàn quốc</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={`${row.customer_state}-${row.customer_unique_id}`}>
            <TableCell className="font-medium">{String(row.customer_state)}</TableCell>
            <TableCell>#{String(row.state_spend_rank)}</TableCell>
            <TableCell title={String(row.customer_unique_id)}>{String(row.customer_unique_id).slice(0, 8)}</TableCell>
            <TableCell className="text-right tabular-nums">{count(Number(row.state_orders))}</TableCell>
            <TableCell className="text-right tabular-nums">{money(Number(row.state_spend))}</TableCell>
            <TableCell className="text-right tabular-nums">{pct(Number(row.national_spend_percentile))}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
