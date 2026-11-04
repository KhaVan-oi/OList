import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { buttonVariants } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { chartFreight, chartGrid, chartMuted, chartSales, chartSlices, chartTick } from '../../../lib/chart.ts'
import { axisMoney, count, money, pct } from '../../../lib/format.ts'
import { cn } from '../../../lib/utils.ts'
import type { Row } from '../../../types/api.ts'
import { getCategoryBrief, getCustomerBrief, getMonthBrief, getOverview, getParetoBrief } from '../services/overviewApi.ts'
import type { OverviewResponse } from '../types/overview.ts'

const tick = { fill: chartTick, fontSize: 10 }

export function OverviewPage() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: getOverview })
  const months = useQuery({ queryKey: ['overview', 'months'], queryFn: getMonthBrief })
  const categories = useQuery({ queryKey: ['overview', 'categories'], queryFn: getCategoryBrief })
  const frequency = useQuery({ queryKey: ['overview', 'frequency'], queryFn: getCustomerBrief })
  const pareto = useQuery({ queryKey: ['overview', 'pareto'], queryFn: getParetoBrief })
  const data = overview.data
  const monthRows = (months.data?.data ?? []).map((row) => ({ ...row, label: `${row.month}/${row.year}` }))
  const paretoRow = pareto.data?.data?.[0]
  const paretoCategories = pareto.data?.categories ?? []

  return (
    <section className="space-y-3">
      <PageHeading title="Tổng quan" />
      <QueryState loading={overview.isLoading} error={overview.error}>
        {data && <Kpi data={data} />}
      </QueryState>

      <div className="grid items-start gap-3 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader>
            <CardTitle>Thời gian</CardTitle>
            <CardAction>
              <Link to="/thoi-gian" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Mở
              </Link>
            </CardAction>
          </CardHeader>
          <CardContent>
            <QueryState loading={months.isLoading} error={months.error}>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={monthRows} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke={chartGrid} />
                    <XAxis dataKey="label" tick={tick} interval="preserveStartEnd" />
                    <YAxis tickFormatter={axisMoney} width={40} tick={tick} />
                    <Tooltip formatter={(value) => money(typeof value === 'number' ? value : Number(value))} />
                    <Line dataKey="product_sales" name="Doanh thu hàng" stroke={chartSales} dot={false} strokeWidth={2} />
                    <Line dataKey="freight_value" name="Cước" stroke={chartFreight} dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </QueryState>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Khu vực</CardTitle>
            <CardAction>
              <Link to="/hang-hoa" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Mở
              </Link>
            </CardAction>
          </CardHeader>
          <CardContent>
            <QueryState loading={categories.isLoading} error={categories.error}>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categories.data?.data ?? []} layout="vertical" margin={{ left: 4, right: 8, top: 0, bottom: 0 }}>
                    <CartesianGrid horizontal={false} stroke={chartGrid} />
                    <XAxis type="number" tickFormatter={axisMoney} tick={tick} />
                    <YAxis type="category" dataKey="category" width={88} tick={tick} />
                    <Tooltip formatter={(value) => money(typeof value === 'number' ? value : Number(value))} />
                    <Bar dataKey="revenue" name="Doanh thu hàng" fill={chartSales} barSize={10} radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </QueryState>
          </CardContent>
        </Card>
      </div>

      <div className="grid items-start gap-3 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader>
            <CardTitle>Pareto mã sản phẩm</CardTitle>
            <CardAction>
              <Link to="/hang-hoa" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Mở
              </Link>
            </CardAction>
          </CardHeader>
          <CardContent>
            <QueryState loading={pareto.isLoading} error={pareto.error}>
              {paretoRow && (
                <div className="grid items-center gap-3 sm:grid-cols-5">
                  <div className="sm:col-span-2">
                    <ParetoDonut row={paretoRow} />
                  </div>
                  <div className="sm:col-span-3">
                    <div className="h-40">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={paretoCategories.slice(0, 6).map(prettyCategory)}
                          layout="vertical"
                          margin={{ left: 4, right: 8, top: 0, bottom: 0 }}
                        >
                          <CartesianGrid horizontal={false} stroke={chartGrid} />
                          <XAxis type="number" tickFormatter={axisMoney} tick={tick} />
                          <YAxis type="category" dataKey="label" width={96} tick={tick} />
                          <Tooltip
                            formatter={(value, _name, item) => {
                              const row = item?.payload as Row | undefined
                              const codes = row?.n_products != null ? count(Number(row.n_products)) : null
                              const amount = money(typeof value === 'number' ? value : Number(value))
                              return [codes ? `${amount} · ${codes} mã` : amount, 'Doanh thu hàng']
                            }}
                          />
                          <Bar dataKey="revenue" name="Doanh thu hàng" radius={[0, 6, 6, 0]} barSize={10}>
                            {paretoCategories.slice(0, 6).map((_, index) => (
                              <Cell key={index} fill={chartSlices[index % chartSlices.length]} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
              )}
            </QueryState>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Khách hàng</CardTitle>
            <CardAction>
              <Link to="/khach" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Mở
              </Link>
            </CardAction>
          </CardHeader>
          <CardContent>
            <QueryState loading={frequency.isLoading} error={frequency.error}>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={(frequency.data?.data ?? []).map(shortTier)} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke={chartGrid} />
                    <XAxis dataKey="label" tick={tick} />
                    <YAxis tickFormatter={(value) => count(Number(value))} width={40} tick={tick} />
                    <Tooltip formatter={(value) => count(typeof value === 'number' ? value : Number(value))} />
                    <Bar dataKey="customers" name="Khách" fill={chartSales} radius={[6, 6, 0, 0]} barSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </QueryState>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

function ParetoDonut({ row }: { row: Row }) {
  const topShare = typeof row.pct_of_total_revenue === 'number' ? row.pct_of_total_revenue : 0
  const topProducts = Number(row.n_top_20pct_products)
  const allProducts = Number(row.n_products)
  const topRevenue = typeof row.top_20pct_revenue === 'number' ? row.top_20pct_revenue : 0
  const totalRevenue = typeof row.total_revenue === 'number' ? row.total_revenue : 0
  const restRevenue = Math.max(0, totalRevenue - topRevenue)
  const slices = [
    { key: 'top', label: 'Top 20% mã', value: topRevenue, fill: chartSales },
    { key: 'rest', label: 'Còn lại', value: restRevenue, fill: chartMuted },
  ]

  return (
    <div className="mx-auto w-full max-w-[11rem] space-y-1">
      <div className="relative h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius={36}
              outerRadius={52}
              paddingAngle={2}
              stroke="none"
            >
              {slices.map((slice) => (
                <Cell key={slice.key} fill={slice.fill} />
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
          <p className="text-lg font-semibold tabular-nums tracking-tight">{pct(topShare)}</p>
          <p className="text-[10px] text-muted-foreground">doanh thu hàng</p>
        </div>
      </div>
      <p className="text-center text-xs tabular-nums text-muted-foreground">
        <span className="font-medium text-foreground">
          {count(topProducts)}/{count(allProducts)}
        </span>{' '}
        mã
      </p>
    </div>
  )
}

function prettyCategory(row: Row) {
  return {
    ...row,
    label: String(row.category ?? '').replaceAll('_', ' '),
  }
}

function Kpi({ data }: { data: OverviewResponse }) {
  const sales = data.sales
  const payment = data.payment
  const gap = data.reconciliation.payment_minus_price_and_freight
  const freightShare = sales.product_sales ? (sales.freight_value / sales.product_sales) * 100 : null
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Doanh thu hàng" value={money(sales.product_sales)} detail={`${count(sales.orders)} đơn`} />
      <Stat label="Cước" value={money(sales.freight_value)} detail={freightShare == null ? undefined : pct(freightShare)} />
      <Stat label="Thanh toán" value={money(payment.payment_value)} detail={`AOV ${money(payment.aov)}`} />
      <Stat label="Lệch TT − (giá+cước)" value={money(gap)} detail={`${count(payment.customers)} khách`} />
    </div>
  )
}

function shortTier(row: Row) {
  const tier = String(row.frequency_tier)
  let label = 'Từ 4 đơn'
  if (tier.includes('1 don')) label = '1 đơn'
  else if (tier.includes('2 don')) label = '2 đơn'
  else if (tier.includes('3 don')) label = '3 đơn'
  return { ...row, label }
}
