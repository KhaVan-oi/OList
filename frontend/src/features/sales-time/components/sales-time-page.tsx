import { useQuery } from '@tanstack/react-query'
import { CalendarDaysIcon, Table2Icon } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Button } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { NativeSelect } from '../../../components/ui/native-select.tsx'
import type { Row } from '../../../types/api.ts'
import { DRILL_MAX, climbTo, drillDepth, drillInto, endpointFor, operationOf, rowLabel, type Operation } from '../depth.ts'
import { getSalesTime } from '../services/salesTimeApi.ts'
import { TimeChart } from './time-chart.tsx'

const grains = [
  ['month', 'Tháng'],
  ['quarter', 'Quý'],
  ['year', 'Năm'],
] as const

export function SalesTimePage() {
  const [params, setParams] = useSearchParams()
  const view = viewOf(params)
  const operation = operationOf(view)
  const depth = drillDepth(view)
  const path = endpointFor(view)
  const query = useQuery({ queryKey: ['sales-time', path], queryFn: () => getSalesTime(path) })
  const rows = (query.data?.data ?? []).map((row) => ({ ...row, label: rowLabel(row, operation) }))
  const canDrill = operation === 'drill' && depth < DRILL_MAX
  const canOpen = operation === 'summary' || operation === 'slice' || canDrill
  const year = selectedYear(operation, view)
  const quarter = operation === 'dice' || operation === 'drill' ? view.get('quarter') ?? '' : ''
  const weekend = view.get('weekend') ?? ''
  const grain = operation === 'summary' ? view.get('grain') ?? 'month' : ''
  const pivot = operation === 'pivot'
  const kpi = view.get('kpi') ?? 'sales'
  const pivotType = view.get('type') ?? 'value'
  const canClimb = operation === 'drill' ? depth > 1 : operation !== 'summary' && !pivot

  function open(row: Row) {
    if (operation === 'drill' && canDrill) {
      setParams(drillInto(view, row))
      return
    }
    if (operation === 'summary') {
      const nextGrain = view.get('grain') ?? 'month'
      const next = new URLSearchParams({ op: 'drill' })
      if (row.year != null) next.set('year', String(row.year))
      if (nextGrain !== 'year' && row.quarter != null) next.set('quarter', String(row.quarter))
      if (nextGrain === 'month' && row.month != null) next.set('month', String(row.month))
      setParams(next)
      return
    }
    if (operation === 'slice' && row.month != null) {
      setParams(new URLSearchParams({ op: 'drill', year: view.get('year') ?? String(row.year ?? ''), month: String(row.month) }))
    }
  }

  function climb() {
    if (operation === 'drill' && depth > 1) {
      setParams(climbTo(view, depth - 1))
      return
    }
    setParams(new URLSearchParams({ op: 'summary', grain: operation === 'drill' ? 'year' : 'month' }))
  }

  return (
    <section className="space-y-4">
      <PageHeading
        title="Thời gian"
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm">
              <span className="inline-flex size-8 items-center justify-center text-muted-foreground" aria-hidden>
                <CalendarDaysIcon className="size-4" />
              </span>
              {pivot ? (
                <>
                  <NativeSelect
                    id="time-kpi"
                    aria-label="Chỉ số"
                    className="min-w-[9rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                    value={kpi}
                    onChange={(event) =>
                      setParams(new URLSearchParams({ op: 'pivot', kpi: event.target.value, type: pivotType }))
                    }
                  >
                    <option value="sales">Doanh thu hàng</option>
                    <option value="freight">Cước</option>
                    <option value="count">Số món</option>
                  </NativeSelect>
                  <span className="h-5 w-px bg-border" aria-hidden />
                  <NativeSelect
                    id="time-pivot-type"
                    aria-label="Kiểu"
                    className="min-w-[6.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                    value={pivotType}
                    onChange={(event) =>
                      setParams(new URLSearchParams({ op: 'pivot', kpi, type: event.target.value }))
                    }
                  >
                    <option value="value">Giá trị</option>
                    <option value="growth">MoM</option>
                  </NativeSelect>
                </>
              ) : (
                <>
                  <NativeSelect
                    id="time-year"
                    aria-label="Năm"
                    className="min-w-[7.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                    value={year}
                    onChange={(event) => setParams(setYear(operation, view, event.target.value))}
                  >
                    <option value="">Toàn kỳ</option>
                    <option value="2016">Năm 2016</option>
                    <option value="2017">Năm 2017</option>
                    <option value="2018">Năm 2018</option>
                  </NativeSelect>
                  {year ? (
                    <>
                      <span className="h-5 w-px bg-border" aria-hidden />
                      <NativeSelect
                        id="time-quarter"
                        aria-label="Quý"
                        className="min-w-[6.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                        value={quarter}
                        onChange={(event) => setParams(setQuarter(operation, view, event.target.value))}
                      >
                        <option value="">Cả năm</option>
                        <option value="1">Q1</option>
                        <option value="2">Q2</option>
                        <option value="3">Q3</option>
                        <option value="4">Q4</option>
                      </NativeSelect>
                    </>
                  ) : null}
                  <span className="h-5 w-px bg-border" aria-hidden />
                  <NativeSelect
                    id="time-weekend"
                    aria-label="Ngày trong tuần"
                    className="min-w-[7.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                    value={weekend}
                    onChange={(event) => setParams(setWeekend(operation, view, event.target.value))}
                  >
                    <option value="">Mọi ngày</option>
                    <option value="0">Ngày thường</option>
                    <option value="1">Cuối tuần</option>
                  </NativeSelect>
                </>
              )}
            </div>

            {!pivot ? (
              <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm">
                <NativeSelect
                  id="time-grain"
                  aria-label="Cấp tổng"
                  className="min-w-[6.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                  value={grain || 'month'}
                  onChange={(event) => setParams(new URLSearchParams({ op: 'summary', grain: event.target.value }))}
                >
                  {grains.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            ) : null}

            <Button
              type="button"
              variant={pivot ? 'default' : 'outline'}
              size="icon-sm"
              aria-label="Xoay tháng × năm"
              aria-pressed={pivot}
              onClick={() =>
                setParams(
                  pivot
                    ? new URLSearchParams({ op: 'summary', grain: 'month' })
                    : new URLSearchParams({ op: 'pivot', kpi: 'sales', type: 'value' }),
                )
              }
            >
              <Table2Icon />
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>{pivot ? 'Xoay tháng × năm' : 'Doanh thu theo thời gian'}</CardTitle>
          {canClimb ? (
            <CardAction>
              <Button type="button" variant="outline" size="sm" onClick={climb}>
                Xem cấp trên
              </Button>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent>
          <QueryState loading={query.isLoading} error={query.error}>
            <TimeChart rows={rows} operation={operation} canDrill={canOpen} onDrill={open} />
          </QueryState>
        </CardContent>
      </Card>
    </section>
  )
}

function viewOf(params: URLSearchParams) {
  const next = new URLSearchParams(params)
  if (next.get('op') === 'rollup') {
    const level = next.get('level')
    const grain = level === '0' ? 'month' : level === '1' ? 'quarter' : 'year'
    return new URLSearchParams({ op: 'summary', grain })
  }
  if (!next.get('op')) next.set('op', 'summary')
  if (next.get('op') === 'summary' && !next.get('grain')) next.set('grain', 'month')
  return next
}

function selectedYear(operation: Operation, params: URLSearchParams) {
  if (operation === 'slice' || operation === 'drill') return params.get('year') ?? ''
  if (operation === 'dice' && params.get('year_from') && params.get('year_from') === params.get('year_to')) {
    return params.get('year_from') ?? ''
  }
  return ''
}

function setYear(operation: Operation, params: URLSearchParams, year: string) {
  if (!year) return new URLSearchParams({ op: 'summary', grain: 'month' })
  if (operation === 'drill' && params.get('quarter')) {
    return new URLSearchParams({ op: 'drill', year, quarter: params.get('quarter') ?? '' })
  }
  if (operation === 'dice') {
    const next = new URLSearchParams(params)
    next.set('op', 'dice')
    next.set('year_from', year)
    next.set('year_to', year)
    return next
  }
  return new URLSearchParams({ op: 'slice', year })
}

function setQuarter(operation: Operation, params: URLSearchParams, quarter: string) {
  const year = selectedYear(operation, params)
  if (!quarter) {
    if (operation === 'drill' && params.get('year')) {
      return new URLSearchParams({ op: 'drill', year: params.get('year') ?? '' })
    }
    if (year) return new URLSearchParams({ op: 'slice', year })
    return new URLSearchParams({ op: 'summary', grain: 'month' })
  }
  if (year) return new URLSearchParams({ op: 'drill', year, quarter })
  const next = new URLSearchParams({ op: 'dice', year_from: '2016', year_to: '2018', quarter })
  const weekend = params.get('weekend')
  if (weekend) next.set('weekend', weekend)
  return next
}

function setWeekend(operation: Operation, params: URLSearchParams, weekend: string) {
  if (operation === 'drill' && params.get('month')) {
    const next = new URLSearchParams(params)
    if (weekend) next.set('weekend', weekend)
    else next.delete('weekend')
    return next
  }
  const year = selectedYear(operation, params)
  if (!weekend) {
    const quarter = operation === 'dice' ? params.get('quarter') ?? '' : ''
    if (quarter && year) return new URLSearchParams({ op: 'drill', year, quarter })
    if (quarter) return new URLSearchParams({ op: 'dice', year_from: '2016', year_to: '2018', quarter })
    if (year) return new URLSearchParams({ op: 'slice', year })
    return new URLSearchParams({ op: 'summary', grain: 'month' })
  }
  const next = new URLSearchParams({ op: 'dice', year_from: year || '2016', year_to: year || '2018', weekend })
  const quarter = params.get('quarter')
  if (quarter && (operation === 'dice' || operation === 'drill')) next.set('quarter', quarter)
  return next
}
