import { useQuery } from '@tanstack/react-query'
import { BoxesIcon, CalendarDaysIcon, ChevronDownIcon, FunnelIcon, TagIcon, XIcon } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Badge } from '../../../components/ui/badge.tsx'
import { Button } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { NativeSelect } from '../../../components/ui/native-select.tsx'
import { chartGrid, chartMuted, chartSales, chartSlices, chartTick } from '../../../lib/chart.ts'
import { axisMoney, money } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import {
  categoryOf,
  defaultDiceCategory,
  defaultDiceStates,
  diceCategoriesOf,
  diceStateChoices,
  diceStatesOf,
  filterStatesOf,
  focusCategoryOf,
  focusOf,
  focusStateOf,
  numberOf,
  pretty,
  quarterOf,
  sellerLabel,
  toggleCode,
  topOf,
  yearOf,
} from '../depth.ts'
import { getSellerCategories, getSellerDice, getSellerPeriods, getTopSellers } from '../services/sellerApi.ts'

const tick = { fill: chartTick, fontSize: 11 }
const stateColor = Object.fromEntries(diceStateChoices.map((code, index) => [code, chartSlices[index % chartSlices.length]]))
type Panel = 'filter' | 'dice' | null
type FilterDropdown = 'category' | 'top' | 'states' | null

export function SellerPage() {
  const [params, setParams] = useSearchParams()
  const category = categoryOf(params)
  const top = topOf(params)
  const year = yearOf(params)
  const quarterRaw = quarterOf(params)
  const diceStates = diceStatesOf(params)
  const filterStates = filterStatesOf(params)
  const focus = focusOf(params)
  const focusState = focusStateOf(params)
  const focusCategory = focusCategoryOf(params)
  const useDice = diceStates.length > 0
  const rawDiceCategories = diceCategoriesOf(params)
  const diceCategories = useDice
    ? rawDiceCategories.length
      ? rawDiceCategories
      : [defaultDiceCategory]
    : []
  const [panel, setPanel] = useState<Panel>(null)
  const [filterDropdown, setFilterDropdown] = useState<FilterDropdown>(null)
  const [draftFilterCategory, setDraftFilterCategory] = useState('')
  const [draftFilterStates, setDraftFilterStates] = useState<string[]>([])
  const [draftTop, setDraftTop] = useState('10')
  const [draftCategories, setDraftCategories] = useState<string[]>([defaultDiceCategory])
  const [draftStates, setDraftStates] = useState<string[]>([...defaultDiceStates])
  const toolbarRef = useRef<HTMLDivElement>(null)
  const sideRef = useRef<HTMLElement>(null)

  const periods = useQuery({
    queryKey: ['seller', 'periods'],
    queryFn: getSellerPeriods,
  })
  const periodOptions = periods.data?.data ?? []
  const yearOptions = [...new Set(periodOptions.map((row) => Number(row.year)).filter((value) => Number.isInteger(value)))].sort()
  const quartersWithData = new Set(
    periodOptions
      .filter((row) => !year || Number(row.year) === Number(year))
      .map((row) => Number(row.quarter))
      .filter((value) => Number.isInteger(value)),
  )
  const quarterOptions = [1, 2, 3, 4]
  const periodsReady = Boolean(periods.data)
  const quarter =
    year && quarterRaw && (!periodsReady || quartersWithData.has(Number(quarterRaw))) ? quarterRaw : ''
  const categories = useQuery({
    queryKey: ['seller', 'categories', year, quarter],
    queryFn: () => getSellerCategories(year, quarter),
  })
  const sellers = useQuery({
    queryKey: ['seller', 'top', top, useDice ? '' : category, useDice ? '' : filterStates.join(','), year, quarter],
    queryFn: () => getTopSellers(top, useDice ? '' : category, year, quarter, useDice ? [] : filterStates),
  })
  const dice = useQuery({
    queryKey: ['seller', 'dice', top, diceCategories.join(','), diceStates.join(','), year, quarter],
    queryFn: () => getSellerDice(top, diceCategories, diceStates, year, quarter),
    enabled: useDice,
  })

  const rankRows = rankSellers(sellers.data?.data ?? [])
  const diceRows = dice.data?.data ?? []
  const viewDiceRows = scopeDiceRows(diceRows, focus, focusState, focusCategory)
  // Một thanh = tổng seller trong khối; bang / danh mục xem ở hai phép chiếu bên.
  const cubeSellerRows = rankSellers(rollupSellers(viewDiceRows))
  const stateTotals = totalsByState(viewDiceRows, diceStates)
  const categoryTotals = totalsByCategory(viewDiceRows, diceCategories)
  const categoryRows = categories.data?.data ?? []
  const loading = useDice ? dice.isLoading || sellers.isLoading : sellers.isLoading
  const error = useDice ? dice.error || sellers.error : sellers.error
  const diceReady = draftCategories.length > 0 && draftStates.length > 0

  useEffect(() => {
    if (!panel) return
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node
      if (toolbarRef.current?.contains(target) || sideRef.current?.contains(target)) return
      setPanel(null)
      setFilterDropdown(null)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [panel])

  function edit(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next)
  }

  function syncFilterDraft() {
    setDraftFilterCategory(category)
    setDraftFilterStates(filterStates)
    setDraftTop(top)
    setFilterDropdown(null)
  }

  function syncDiceDraft() {
    setDraftCategories(
      useDice
        ? diceCategories
        : category
          ? category.split(',').map((item) => item.trim()).filter(Boolean)
          : [defaultDiceCategory],
    )
    setDraftStates(useDice && diceStates.length ? diceStates : [...defaultDiceStates])
    setDraftTop(top)
    setFilterDropdown(null)
  }

  function toggleFilterPanel() {
    if (useDice) return
    if (panel === 'filter') {
      setPanel(null)
      setFilterDropdown(null)
      return
    }
    syncFilterDraft()
    setPanel('filter')
  }

  function openDicePanel() {
    syncDiceDraft()
    setPanel('dice')
  }

  function toggleDicePanel() {
    if (panel === 'dice') {
      setPanel(null)
      return
    }
    openDicePanel()
  }

  function applyFilter() {
    if (useDice) return
    edit({
      category: draftFilterCategory,
      states: draftFilterStates.join(','),
      top: draftTop === '10' ? '' : draftTop,
      focus: '',
    })
    setPanel(null)
    setFilterDropdown(null)
  }

  function clearFilter() {
    if (useDice) return
    edit({
      category: '',
      states: '',
      top: '',
      focus: '',
    })
    setDraftFilterCategory('')
    setDraftFilterStates([])
    setDraftTop('10')
    setPanel(null)
    setFilterDropdown(null)
  }

  function applyDice() {
    if (!diceReady) return
    edit({
      box: draftStates.join(','),
      category: draftCategories.join(','),
      top: draftTop === '10' ? '' : draftTop,
      states: '',
      ...clearCubeFocus(),
    })
    setPanel(null)
    setFilterDropdown(null)
  }

  function exitDice() {
    edit({
      box: '',
      category: diceCategories.length === 1 ? diceCategories[0] : '',
      ...clearCubeFocus(),
    })
    setPanel(null)
    setFilterDropdown(null)
  }

  function clearCubeFocus() {
    return { focus: '', fstate: '', fcat: '' }
  }

  function pickSeller(sellerId: string) {
    if (!useDice) {
      edit({ focus: focus === sellerId ? '' : sellerId })
      return
    }
    edit({
      ...clearCubeFocus(),
      focus: focus === sellerId ? '' : sellerId,
    })
  }

  function pickState(code: string) {
    edit({
      ...clearCubeFocus(),
      fstate: focusState === code ? '' : code,
    })
  }

  function pickCategory(code: string) {
    edit({
      ...clearCubeFocus(),
      fcat: focusCategory === code ? '' : code,
    })
  }

  const filterActive = !useDice && (panel === 'filter' || Boolean(category) || filterStates.length > 0 || top !== '10')
  const diceActive = panel === 'dice' || useDice
  const filterDirty =
    draftTop !== top ||
    draftFilterCategory !== category ||
    draftFilterStates.join(',') !== filterStates.join(',')

  return (
    <section className="space-y-4">
      <PageHeading
        title="Người bán"
        actions={
          <div className="flex items-center gap-2" ref={toolbarRef}>
            <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm">
              <span className="inline-flex size-8 items-center justify-center text-muted-foreground" aria-hidden>
                <CalendarDaysIcon className="size-4" />
              </span>
              <NativeSelect
                id="seller-year"
                aria-label="Năm"
                className="min-w-[7.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                value={year}
                onChange={(event) => edit({ year: event.target.value, quarter: '', focus: '' })}
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
                    id="seller-quarter"
                    aria-label="Quý"
                    className="min-w-[6.5rem] border-0 bg-transparent shadow-none focus-visible:ring-0"
                    value={quarter}
                    onChange={(event) => edit({ quarter: event.target.value, focus: '' })}
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
            {!useDice && (
              <Button
                type="button"
                variant={filterActive ? 'default' : 'outline'}
                size="icon-sm"
                aria-label="Lọc"
                aria-expanded={panel === 'filter'}
                aria-haspopup="menu"
                onClick={toggleFilterPanel}
              >
                <FunnelIcon />
              </Button>
            )}
            <Button
              type="button"
              variant={diceActive ? 'default' : 'outline'}
              size="icon-sm"
              aria-label={useDice ? 'Đổi khối' : 'Xem khối'}
              aria-expanded={panel === 'dice'}
              aria-haspopup="dialog"
              onClick={toggleDicePanel}
            >
              <BoxesIcon />
            </Button>
          </div>
        }
      />

      <div className="flex items-stretch gap-4">
        <div className="min-w-0 flex-1 space-y-4">
          <div className={`grid items-start gap-4 ${useDice ? 'xl:grid-cols-5' : ''}`}>
            <Card className={useDice ? 'xl:col-span-3' : undefined}>
              <CardHeader>
                <CardTitle>{useDice ? 'Khối theo người bán' : 'Top người bán'}</CardTitle>
                {useDice && focus ? (
                  <CardAction>
                    <Button type="button" variant="outline" size="sm" onClick={() => edit(clearCubeFocus())}>
                      Xem tất cả người bán
                    </Button>
                  </CardAction>
                ) : useDice && (focusState || focusCategory) ? (
                  <CardAction>
                    <SliceTag label={focusState || pretty(focusCategory)} />
                  </CardAction>
                ) : null}
              </CardHeader>
              <CardContent>
                <QueryState loading={loading} error={error}>
                  <div className="h-96">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={useDice ? cubeSellerRows : rankRows}
                        layout="vertical"
                        margin={{ left: 8, right: 12 }}
                      >
                        <CartesianGrid horizontal={false} stroke={chartGrid} />
                        <XAxis type="number" tickFormatter={axisMoney} tick={tick} />
                        <YAxis type="category" dataKey="label" width={56} tick={tick} />
                        <Tooltip
                          formatter={(value) => money(typeof value === 'number' ? value : Number(value))}
                          labelFormatter={(_label, payload) => String(payload?.[0]?.payload?.seller_id ?? '')}
                        />
                        <Bar
                          dataKey="revenue"
                          name="Doanh thu hàng"
                          radius={[0, 6, 6, 0]}
                          barSize={14}
                          cursor="pointer"
                          onClick={(item) => {
                            const id = String((item as { seller_id?: string })?.seller_id ?? (item as { payload?: Row })?.payload?.seller_id ?? '')
                            if (id) pickSeller(id)
                          }}
                        >
                          {(useDice ? cubeSellerRows : rankRows).map((row) => (
                            <Cell
                              key={String(row.seller_id)}
                              fill={focus && String(row.seller_id) === focus ? chartSales : focus ? chartMuted : chartSales}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </QueryState>
              </CardContent>
            </Card>

            {useDice && (
              <div className="space-y-3 xl:col-span-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Bang</CardTitle>
                    {focusState ? (
                      <CardAction>
                        <Button type="button" variant="outline" size="sm" onClick={() => edit(clearCubeFocus())}>
                          Xem tất cả bang
                        </Button>
                      </CardAction>
                    ) : focus || focusCategory ? (
                      <CardAction>
                        <SliceTag label={focus ? sellerLabel(focus) : pretty(focusCategory)} />
                      </CardAction>
                    ) : null}
                  </CardHeader>
                  <CardContent>
                    <QueryState loading={dice.isLoading} error={dice.error}>
                      <div className="h-36">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={stateTotals} margin={{ left: 4, right: 4, top: 4, bottom: 0 }}>
                            <CartesianGrid vertical={false} stroke={chartGrid} />
                            <XAxis dataKey="state" tick={tick} />
                            <YAxis tickFormatter={axisMoney} width={44} tick={tick} />
                            <Tooltip formatter={(value) => money(typeof value === 'number' ? value : Number(value))} />
                            <Bar
                              dataKey="revenue"
                              name="Doanh thu hàng"
                              radius={[6, 6, 0, 0]}
                              barSize={22}
                              cursor="pointer"
                              onClick={(item) => {
                                const code = String((item as { state?: string })?.state ?? (item as { payload?: { state?: string } })?.payload?.state ?? '')
                                if (code) pickState(code)
                              }}
                            >
                              {stateTotals.map((row) => (
                                <Cell
                                  key={row.state}
                                  fill={
                                    focusState && row.state !== focusState
                                      ? chartMuted
                                      : stateColor[row.state] ?? chartSales
                                  }
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </QueryState>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Danh mục</CardTitle>
                    {focusCategory ? (
                      <CardAction>
                        <Button type="button" variant="outline" size="sm" onClick={() => edit(clearCubeFocus())}>
                          Xem tất cả danh mục
                        </Button>
                      </CardAction>
                    ) : focus || focusState ? (
                      <CardAction>
                        <SliceTag label={focus ? sellerLabel(focus) : focusState} />
                      </CardAction>
                    ) : null}
                  </CardHeader>
                  <CardContent>
                    <QueryState loading={dice.isLoading} error={dice.error}>
                      <CategoryDonut
                        rows={categoryTotals}
                        activeKey={focusCategory}
                        onPick={pickCategory}
                      />
                    </QueryState>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>

        {panel === 'filter' && !useDice && (
          <aside
            ref={sideRef}
            className="flex w-72 shrink-0 flex-col overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-[0_8px_24px_rgba(28,29,33,0.04)]"
          >
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <p className="text-sm font-semibold">Bộ lọc</p>
              <button
                type="button"
                aria-label="Đóng bộ lọc"
                className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={() => {
                  setPanel(null)
                  setFilterDropdown(null)
                }}
              >
                <XIcon className="size-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2">
              <FilterDropdownField
                label="Danh mục"
                summary={draftFilterCategory ? pretty(draftFilterCategory) : 'Toàn kho'}
                open={filterDropdown === 'category'}
                onToggle={() => setFilterDropdown(filterDropdown === 'category' ? null : 'category')}
              >
                <CheckboxOption
                  label="Toàn kho"
                  checked={!draftFilterCategory}
                  onChange={() => setDraftFilterCategory('')}
                />
                {categoryRows.map((row) => {
                  const code = String(row.category ?? '')
                  return (
                    <CheckboxOption
                      key={code}
                      label={pretty(code)}
                      checked={draftFilterCategory === code}
                      onChange={() => setDraftFilterCategory(code)}
                    />
                  )
                })}
              </FilterDropdownField>
              <FilterDropdownField
                label="Top"
                summary={`Top ${draftTop}`}
                open={filterDropdown === 'top'}
                onToggle={() => setFilterDropdown(filterDropdown === 'top' ? null : 'top')}
              >
                {(['5', '10', '20'] as const).map((value) => (
                  <CheckboxOption
                    key={value}
                    label={`Top ${value}`}
                    checked={draftTop === value}
                    onChange={() => setDraftTop(value)}
                  />
                ))}
              </FilterDropdownField>
              <FilterDropdownField
                label="Bang khách"
                summary={draftFilterStates.length ? draftFilterStates.join(', ') : 'Mọi bang'}
                open={filterDropdown === 'states'}
                onToggle={() => setFilterDropdown(filterDropdown === 'states' ? null : 'states')}
              >
                {diceStateChoices.map((code) => (
                  <CheckboxOption
                    key={code}
                    label={code}
                    checked={draftFilterStates.includes(code)}
                    onChange={() => setDraftFilterStates(toggleCode(draftFilterStates, code).split(',').filter(Boolean))}
                  />
                ))}
              </FilterDropdownField>
            </div>
            <div className="mt-auto flex items-center justify-end gap-2 border-t border-border px-3 py-2">
              <Button type="button" variant="outline" size="sm" onClick={clearFilter}>
                Bỏ lọc
              </Button>
              <Button type="button" size="sm" disabled={!filterDirty} onClick={applyFilter}>
                Áp dụng
              </Button>
            </div>
          </aside>
        )}

        {panel === 'dice' && (
          <aside
            ref={sideRef}
            className="flex w-72 shrink-0 flex-col overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-[0_8px_24px_rgba(28,29,33,0.04)]"
          >
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <p className="text-sm font-semibold">Khối</p>
              <button
                type="button"
                aria-label="Đóng khối"
                className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={() => {
                  setPanel(null)
                  setFilterDropdown(null)
                }}
              >
                <XIcon className="size-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2">
              <FilterDropdownField
                label="Top"
                summary={`Top ${draftTop}`}
                open={filterDropdown === 'top'}
                onToggle={() => setFilterDropdown(filterDropdown === 'top' ? null : 'top')}
              >
                {(['5', '10', '20'] as const).map((value) => (
                  <CheckboxOption
                    key={value}
                    label={`Top ${value}`}
                    checked={draftTop === value}
                    onChange={() => setDraftTop(value)}
                  />
                ))}
              </FilterDropdownField>
              <FilterDropdownField
                label="Danh mục"
                summary={
                  draftCategories.length
                    ? draftCategories.length <= 2
                      ? draftCategories.map(pretty).join(', ')
                      : `${draftCategories.length} danh mục`
                    : 'Chưa chọn'
                }
                open={filterDropdown === 'category'}
                onToggle={() => setFilterDropdown(filterDropdown === 'category' ? null : 'category')}
              >
                {categoryRows.map((row) => {
                  const code = String(row.category ?? '')
                  return (
                    <CheckboxOption
                      key={code}
                      label={pretty(code)}
                      checked={draftCategories.includes(code)}
                      onChange={() => setDraftCategories(toggleCode(draftCategories, code).split(',').filter(Boolean))}
                    />
                  )
                })}
              </FilterDropdownField>
              <FilterDropdownField
                label="Bang khách"
                summary={draftStates.length ? draftStates.join(', ') : 'Chưa chọn'}
                open={filterDropdown === 'states'}
                onToggle={() => setFilterDropdown(filterDropdown === 'states' ? null : 'states')}
              >
                {diceStateChoices.map((code) => (
                  <CheckboxOption
                    key={code}
                    label={code}
                    checked={draftStates.includes(code)}
                    onChange={() => setDraftStates(toggleCode(draftStates, code).split(',').filter(Boolean))}
                  />
                ))}
              </FilterDropdownField>
            </div>
            <div className="mt-auto flex items-center justify-end gap-2 border-t border-border px-3 py-2">
              {useDice ? (
                <Button type="button" variant="outline" size="sm" onClick={exitDice}>
                  Bỏ khối
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setPanel(null)
                    setFilterDropdown(null)
                  }}
                >
                  Hủy
                </Button>
              )}
              <Button type="button" size="sm" disabled={!diceReady} onClick={applyDice}>
                Áp dụng
              </Button>
            </div>
          </aside>
        )}
      </div>
    </section>
  )
}

function FilterDropdownField({
  label,
  summary,
  open,
  onToggle,
  children,
}: {
  label: string
  summary: string
  open: boolean
  onToggle: () => void
  children: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <button
        type="button"
        onClick={onToggle}
        className="flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 text-left text-sm"
      >
        <span className="truncate">{summary}</span>
        <ChevronDownIcon className={`size-3.5 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? <div className="max-h-44 space-y-0.5 overflow-y-auto rounded-lg border border-border p-1.5">{children}</div> : null}
    </div>
  )
}

function CheckboxOption({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: () => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted">
      <input type="checkbox" className="size-4 accent-primary" checked={checked} onChange={onChange} />
      <span className="truncate">{label}</span>
    </label>
  )
}

function SliceTag({ label }: { label: string }) {
  return (
    <Badge variant="secondary" className="max-w-[14rem] gap-1 truncate">
      <TagIcon className="size-3.5 shrink-0" />
      <span className="truncate">{label}</span>
    </Badge>
  )
}

type SellerRow = Row & { rank: number; label?: string }

function rankSellers(rows: Row[]): SellerRow[] {
  return rows.map((row, index) => ({
    ...row,
    rank: index + 1,
    label: `#${index + 1}`,
  }))
}

function rollupSellers(rows: Row[]): Row[] {
  const bySeller = new Map<string, number>()
  for (const row of rows) {
    const id = String(row.seller_id ?? '')
    if (!id) continue
    bySeller.set(id, (bySeller.get(id) ?? 0) + (numberOf(row.revenue) ?? 0))
  }
  return [...bySeller.entries()]
    .map(([seller_id, revenue]) => ({ seller_id, revenue }))
    .sort((a, b) => Number(b.revenue) - Number(a.revenue))
}

function scopeDiceRows(rows: Row[], sellerId: string, state: string, category: string) {
  return rows.filter((row) => {
    if (sellerId && String(row.seller_id ?? '') !== sellerId) return false
    if (state && String(row.customer_state ?? '') !== state) return false
    if (category && String(row.category ?? '') !== category) return false
    return true
  })
}

function totalsByState(rows: Row[], states: string[]) {
  return states.map((state) => ({
    state,
    revenue: rows
      .filter((row) => String(row.customer_state ?? '') === state)
      .reduce((sum, row) => sum + (numberOf(row.revenue) ?? 0), 0),
  }))
}

function totalsByCategory(rows: Row[], categories: string[]) {
  const order = categories.length
    ? categories
    : [...new Set(rows.map((row) => String(row.category ?? '')).filter(Boolean))]
  return order
    .map((category, index) => ({
      key: category,
      label: pretty(category),
      revenue: rows
        .filter((row) => String(row.category ?? '') === category)
        .reduce((sum, row) => sum + (numberOf(row.revenue) ?? 0), 0),
      fill: chartSlices[index % chartSlices.length],
    }))
    .filter((row) => row.revenue > 0)
}

function CategoryDonut({
  rows,
  activeKey,
  onPick,
}: {
  rows: { key: string; label: string; revenue: number; fill: string }[]
  activeKey?: string
  onPick?: (key: string) => void
}) {
  const total = rows.reduce((sum, row) => sum + row.revenue, 0)
  if (!rows.length || total <= 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">Trống</p>
  }

  return (
    <div className="space-y-2">
      <div className="relative mx-auto h-36 w-full max-w-[11rem]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="revenue"
              nameKey="label"
              innerRadius={38}
              outerRadius={56}
              paddingAngle={rows.length > 1 ? 2 : 0}
              stroke="none"
              cursor={onPick ? 'pointer' : undefined}
              onClick={(_, index) => {
                const key = rows[index]?.key
                if (key && onPick) onPick(key)
              }}
            >
              {rows.map((row) => (
                <Cell
                  key={row.key}
                  fill={activeKey && row.key !== activeKey ? chartMuted : row.fill}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [
                money(typeof value === 'number' ? value : Number(value)),
                'Doanh thu hàng',
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-sm font-semibold tabular-nums tracking-tight">{money(total)}</p>
          <p className="text-[10px] text-muted-foreground">Doanh thu hàng</p>
        </div>
      </div>
      <div className="max-h-24 space-y-1 overflow-y-auto text-sm">
        {rows.map((row) => {
          const share = total ? (row.revenue / total) * 100 : 0
          const muted = Boolean(activeKey && row.key !== activeKey)
          return (
            <button
              key={row.key}
              type="button"
              className={`flex w-full items-center gap-2 rounded-md px-1 py-0.5 text-left hover:bg-muted ${muted ? 'opacity-45' : ''}`}
              onClick={() => onPick?.(row.key)}
            >
              <span className="size-2 shrink-0 rounded-full" style={{ background: row.fill }} />
              <p className="min-w-0 flex-1 truncate text-xs font-medium">{row.label}</p>
              <p className="shrink-0 text-[11px] text-muted-foreground tabular-nums">
                {share.toFixed(0)}%
              </p>
            </button>
          )
        })}
      </div>
    </div>
  )
}

