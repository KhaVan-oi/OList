import { useQuery } from '@tanstack/react-query'
import { CalendarDaysIcon, ChevronLeftIcon, ChevronRightIcon, TagIcon } from 'lucide-react'
import { type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Badge } from '../../../components/ui/badge.tsx'
import { Button } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { NativeSelect } from '../../../components/ui/native-select.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { Table, TableBody, TableCell, TableRow } from '../../../components/ui/table.tsx'
import { count, money, pct } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import {
  PAGE_SIZE,
  RANK_ALL,
  RANK_TOP,
  categoryOf,
  fullRanksOf,
  numberOf,
  pageOf,
  periodQueryOf,
  pretty,
  quarterOf,
  stateOf,
  yearOf,
} from '../depth.ts'
import { getProductGeo } from '../services/productGeoApi.ts'
import { PlaceChart } from './product-chart.tsx'

function joinQuery(...parts: string[]) {
  return parts.filter(Boolean).join('&')
}

export function ProductGeoPage() {
  const [params, setParams] = useSearchParams()
  const state = stateOf(params)
  const category = categoryOf(params)
  const fullRanks = fullRanksOf(params)
  const year = yearOf(params)
  const quarterRaw = quarterOf(params)
  const categoryQuery = category ? `category=${encodeURIComponent(category)}` : ''
  const rankLimit = category || fullRanks ? RANK_ALL : RANK_TOP
  const periods = useQuery({
    queryKey: ['product-geo', 'periods'],
    queryFn: () => getProductGeo('/api/product-geo/periods'),
  })
  const yearOptions = [...new Set((periods.data?.data ?? []).map((row) => Number(row.year)).filter((value) => Number.isInteger(value)))].sort()
  const quartersWithData = new Set(
    (periods.data?.data ?? [])
      .filter((row) => !year || Number(row.year) === Number(year))
      .map((row) => Number(row.quarter))
      .filter((value) => Number.isInteger(value)),
  )
  const quarterOptions = [1, 2, 3, 4]
  const periodsReady = Boolean(periods.data)
  const quarter =
    year && quarterRaw && (!periodsReady || quartersWithData.has(Number(quarterRaw))) ? quarterRaw : ''
  const periodQuery = periodQueryOf(year, quarter)
  const summary = useQuery({
    queryKey: ['product-geo', 'summary', category, year, quarter],
    queryFn: () => getProductGeo(`/api/product-geo/summary?${joinQuery(categoryQuery, periodQuery)}`),
    enabled: !state,
  })
  const states = useQuery({
    queryKey: ['product-geo', 'states', category, year, quarter],
    queryFn: () => getProductGeo(`/api/product-geo/states?${joinQuery(categoryQuery, periodQuery)}`),
  })
  const cities = useQuery({
    queryKey: ['product-geo', 'cities', state, category, year, quarter],
    queryFn: () => getProductGeo(`/api/product-geo/drilldown?${joinQuery(`state=${state}`, categoryQuery, periodQuery)}`),
    enabled: Boolean(state),
  })
  const categories = useQuery({
    queryKey: ['product-geo', 'categories', year, quarter],
    queryFn: () => getProductGeo(`/api/product-geo/categories?${joinQuery('limit=200', periodQuery)}`),
  })
  const ranks = useQuery({
    queryKey: ['product-geo', 'rank', state, rankLimit, year, quarter],
    queryFn: () =>
      getProductGeo(`/api/product-geo/rank?${joinQuery(`state=${state}`, `limit=${rankLimit}`, periodQuery)}`),
    enabled: Boolean(state),
  })

  const placeQuery = state ? cities : states
  const placeRows = (placeQuery.data?.data ?? []).map((row) => ({
    ...row,
    label: state ? pretty(String(row.customer_city ?? '')) : String(row.customer_state ?? ''),
  }))
  const { page, pages } = pageOf(params, placeRows.length)
  const shown = placeRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const categorySource = state ? ranks.data?.data ?? [] : categories.data?.data ?? []
  const categoryRows = slicedRows(categorySource, category)
  const { page: catPage, pages: catPages } = pageOf(params, categoryRows.length, 'cpage')
  const shownCategories = category ? categoryRows : categoryRows.slice((catPage - 1) * PAGE_SIZE, catPage * PAGE_SIZE)
  const headerRow = state
    ? (states.data?.data ?? []).find((row) => row.customer_state === state)
    : summary.data?.data?.[0]
  const revenue = numberOf(headerRow?.total_revenue ?? headerRow?.revenue)
  const freight = numberOf(headerRow?.total_freight ?? headerRow?.freight)
  const orders = numberOf(headerRow?.orders_with_items ?? headerRow?.orders)
  const ratio = revenue ? ((freight ?? 0) / revenue) * 100 : null

  function edit(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    next.delete('op')
    next.delete('level')
    next.delete('page')
    next.delete('cpage')
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next)
  }

  function move(nextPage: number, key = 'page') {
    const next = new URLSearchParams(params)
    if (nextPage <= 1) next.delete(key)
    else next.set(key, String(nextPage))
    setParams(next)
  }

  return (
    <section className="space-y-4">
      <PageHeading
        title="Khu vực"
        actions={
          <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm">
            <span className="inline-flex size-8 items-center justify-center text-muted-foreground" aria-hidden>
              <CalendarDaysIcon className="size-4" />
            </span>
            <NativeSelect
              id="goods-year"
              aria-label="Năm"
              className="min-w-[7.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
              value={year}
              onChange={(event) => edit({ year: event.target.value, quarter: '' })}
            >
              <option value="">Toàn kỳ</option>
              {yearOptions.map((value) => (
                <option key={value} value={value}>{`Năm ${value}`}</option>
              ))}
            </NativeSelect>
            {year ? (
              <>
                <span className="h-5 w-px bg-border" aria-hidden />
                <NativeSelect
                  id="goods-quarter"
                  aria-label="Quý"
                  className="min-w-[6.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                  value={quarter}
                  onChange={(event) => edit({ quarter: event.target.value })}
                >
                  <option value="">Cả năm</option>
                  {quarterOptions.map((value) => (
                    <option key={value} value={value} disabled={!quartersWithData.has(value)}>
                      {`Q${value}`}
                    </option>
                  ))}
                </NativeSelect>
              </>
            ) : null}
          </div>
        }
      />
      <QueryState loading={Boolean(state ? states.isLoading : summary.isLoading)} error={state ? states.error : summary.error}>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Doanh thu hàng" value={money(revenue)} />
          <Stat label="Cước" value={money(freight)} />
          <Stat label="Cước / giá" value={pct(ratio)} />
          <Stat label="Đơn" value={count(orders)} />
        </div>
      </QueryState>
      <div className="grid items-start gap-4 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader>
            <CardTitle>{state ? `Thành phố của ${state}` : 'Bang'}</CardTitle>
            {state || category ? (
              <CardAction className="flex flex-wrap items-center justify-end gap-2">
                {category ? (
                  <Badge variant="secondary" className="max-w-[14rem] gap-1 truncate">
                    <TagIcon className="size-3.5 shrink-0" />
                    <span className="truncate">{pretty(category)}</span>
                  </Badge>
                ) : null}
                {state ? (
                  <Button type="button" variant="outline" size="sm" onClick={() => edit({ state: '', full: '' })}>
                    Xem toàn kho
                  </Button>
                ) : null}
              </CardAction>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-4">
            <QueryState loading={placeQuery.isLoading} error={placeQuery.error}>
              <PlaceChart rows={shown} onOpen={state ? undefined : (row) => edit({ state: String(row.customer_state ?? '') })} />
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" size="icon-sm" aria-label="Trang trước" disabled={page <= 1} onClick={() => move(page - 1)}>
                  <ChevronLeftIcon />
                </Button>
                <span className="text-xs text-muted-foreground">
                  {placeRows.length === 0 ? '0' : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(placeRows.length, page * PAGE_SIZE)}`} / {count(placeRows.length)}
                </span>
                <Button type="button" variant="outline" size="icon-sm" aria-label="Trang sau" disabled={page >= pages} onClick={() => move(page + 1)}>
                  <ChevronRightIcon />
                </Button>
              </div>
            </QueryState>
          </CardContent>
        </Card>
        <div className="space-y-4 xl:col-span-2">
          <SideList
            title={state ? `Danh mục tại ${state}` : 'Danh mục'}
            loading={state ? ranks.isLoading : categories.isLoading}
            error={state ? ranks.error : categories.error}
            rows={shownCategories}
            labelOf={(row) => pretty(String(row.category ?? ''))}
            active={(row) => row.category === category}
            onPick={category ? undefined : (row) => edit({ category: String(row.category ?? '') })}
            extra={state ? (row) => String(row.rank_in_state ?? '') : undefined}
            action={
              category ? (
                <Button type="button" variant="outline" size="sm" onClick={() => edit({ category: '' })}>
                  Xem tất cả danh mục
                </Button>
              ) : state && !fullRanks && categoryRows.length >= RANK_TOP ? (
                <Button type="button" variant="outline" size="sm" onClick={() => edit({ full: '1' })}>
                  Xem thêm danh mục
                </Button>
              ) : state && fullRanks ? (
                <Button type="button" variant="outline" size="sm" onClick={() => edit({ full: '' })}>
                  Thu gọn
                </Button>
              ) : undefined
            }
            page={category || (state && !fullRanks) ? undefined : catPage}
            pages={category || (state && !fullRanks) ? undefined : catPages}
            total={category || (state && !fullRanks) ? undefined : categoryRows.length}
            onPage={category || (state && !fullRanks) ? undefined : (nextPage) => move(nextPage, 'cpage')}
          />
        </div>
      </div>
    </section>
  )
}

function SideList({
  title,
  loading,
  error,
  rows,
  labelOf,
  titleOf,
  active,
  onPick,
  extra,
  action,
  page,
  pages,
  total,
  onPage,
}: {
  title: string
  loading: boolean
  error: Error | null
  rows: Row[]
  labelOf: (row: Row) => string
  titleOf?: (row: Row) => string
  active?: (row: Row) => boolean
  onPick?: (row: Row) => void
  extra?: (row: Row) => string
  action?: ReactNode
  page?: number
  pages?: number
  total?: number
  onPage?: (page: number) => void
}) {
  const start = total && page ? (total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1) : 0
  const end = total && page ? Math.min(total, page * PAGE_SIZE) : 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="space-y-3">
        <QueryState loading={loading} error={error}>
          <Table className="table-fixed">
            <TableBody>
              {rows.map((row) => (
                <TableRow key={`${labelOf(row)}-${extra?.(row) ?? ''}`}>
                  {extra && <TableCell className="w-8 text-muted-foreground">{extra(row)}</TableCell>}
                  <TableCell className="w-full max-w-0" title={titleOf?.(row) ?? labelOf(row)}>
                    {onPick ? (
                      <Button
                        variant="link"
                        size="sm"
                        className={`inline-block h-auto max-w-full truncate px-0 text-left ${active?.(row) ? 'font-semibold' : ''}`}
                        onClick={() => onPick(row)}
                      >
                        {labelOf(row)}
                      </Button>
                    ) : (
                      <span className="block truncate">{labelOf(row)}</span>
                    )}
                  </TableCell>
                  <TableCell className="w-28 text-right tabular-nums">{money(numberOf(row.revenue))}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {onPage && page != null && pages != null && total != null && (
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="icon-sm" aria-label="Trang trước" disabled={page <= 1} onClick={() => onPage(page - 1)}>
                <ChevronLeftIcon />
              </Button>
              <span className="text-xs text-muted-foreground">{start}–{end} / {count(total)}</span>
              <Button type="button" variant="outline" size="icon-sm" aria-label="Trang sau" disabled={page >= pages} onClick={() => onPage(page + 1)}>
                <ChevronRightIcon />
              </Button>
            </div>
          )}
        </QueryState>
      </CardContent>
    </Card>
  )
}

function slicedRows(rows: Row[], category: string) {
  if (!category) return rows
  const matched = rows.filter((row) => row.category === category)
  if (matched.length) return matched
  return [{ category, revenue: null }]
}
