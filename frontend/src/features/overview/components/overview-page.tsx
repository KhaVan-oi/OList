import { useQuery } from '@tanstack/react-query'
import { ArrowRightIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { buttonVariants } from '../../../components/ui/button.tsx'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { chartGrid, chartSales, chartTick } from '../../../lib/chart.ts'
import { axisMoney, count, money, pct } from '../../../lib/format.ts'
import { cn } from '../../../lib/utils.ts'
import { CustomerChart } from '../../customer-payment/components/customer-chart.tsx'
import { getCustomerDrilldown } from '../../customer-payment/services/customerPaymentApi.ts'
import { getTopSellers } from '../../seller/services/sellerApi.ts'
import { rowLabel } from '../../sales-time/depth.ts'
import { TimeChart } from '../../sales-time/components/time-chart.tsx'
import { getCategoryBrief, getMonthBrief, getOverview } from '../services/overviewApi.ts'
import type { OverviewResponse } from '../types/overview.ts'

const tick = { fill: chartTick, fontSize: 10 }

export function OverviewPage() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: getOverview })
  const months = useQuery({ queryKey: ['overview', 'months'], queryFn: getMonthBrief })
  const categories = useQuery({ queryKey: ['overview', 'categories'], queryFn: getCategoryBrief })
  // Ô Khách hàng dùng đúng truy vấn mặc định của tab Khách hàng (chiều khách, measure Số khách)
  const customerChart = useQuery({
    queryKey: ['customer-payment', 'drilldown', 'dim=customer'],
    queryFn: () => getCustomerDrilldown('dim=customer'),
  })
  // Ô Người bán dùng đúng truy vấn xếp hạng mặc định của tab Người bán (top 10, toàn kỳ)
  const sellers = useQuery({
    queryKey: ['seller', 'top', '10', '', '', '', ''],
    queryFn: () => getTopSellers('10', '', '', '', []),
  })
  const data = overview.data
  // Cùng nhãn và cột + đường MoM với biểu đồ Doanh thu ở tab Thời gian
  const monthRows = (months.data?.data ?? []).map((row) => ({ ...row, label: rowLabel(row, 'timeanalysis') }))
  const sellerRows = (sellers.data?.data ?? []).map((row, index) => ({ ...row, label: `#${index + 1}` }))

  return (
    <section className="space-y-3">
      <PageHeading
        title="Tổng quan"
        actions={
          <Link to="/quyet-dinh" className={cn(buttonVariants({ size: 'sm' }))}>
            Quyết định nhập hàng
            <ArrowRightIcon />
          </Link>
        }
      />
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
              <TimeChart
                rows={monthRows}
                operation="timeanalysis"
                activeKpi="sales"
                canDrill={false}
                onDrill={() => {}}
                heightClass="h-44"
              />
            </QueryState>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Danh mục</CardTitle>
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
            <CardTitle>Người bán</CardTitle>
            <CardAction>
              <Link to="/seller" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                Mở
              </Link>
            </CardAction>
          </CardHeader>
          <CardContent>
            <QueryState loading={sellers.isLoading} error={sellers.error}>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sellerRows} layout="vertical" margin={{ left: 8, right: 12, top: 0, bottom: 0 }}>
                    <CartesianGrid horizontal={false} stroke={chartGrid} />
                    <XAxis type="number" tickFormatter={axisMoney} tick={tick} />
                    <YAxis type="category" dataKey="label" width={36} tick={tick} interval={0} />
                    <Tooltip
                      formatter={(value) => money(typeof value === 'number' ? value : Number(value))}
                      labelFormatter={(_label, payload) => String(payload?.[0]?.payload?.seller_id ?? '')}
                    />
                    <Bar dataKey="revenue" name="Doanh thu hàng" fill={chartSales} radius={[0, 6, 6, 0]} barSize={8} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
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
            <QueryState loading={customerChart.isLoading} error={customerChart.error}>
              <CustomerChart rows={customerChart.data?.data ?? []} kpi="customers" heightClass="h-40" />
            </QueryState>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

function Kpi({ data }: { data: OverviewResponse }) {
  const sales = data.sales
  const payment = data.payment
  const customers = data.customers
  const freightShare = sales.product_sales ? (sales.freight_value / sales.product_sales) * 100 : null
  const buyers = customers.one_time + customers.repeat_buyers
  const repeatRate = buyers ? (customers.repeat_buyers / buyers) * 100 : null
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Doanh thu hàng" value={`${money(sales.product_sales)} R$`} detail={`${count(sales.orders)} đơn đã giao`} />
        <Stat label="Giá trị đơn trung bình" value={`${money(payment.aov)} R$`} detail="Đã gồm cước vận chuyển" />
        <Stat
          label="Khách hàng"
          value={count(payment.customers)}
          detail={repeatRate == null ? undefined : `${pct(repeatRate)} mua lại`}
        />
        <Stat
          label="Cước vận chuyển"
          value={`${money(sales.freight_value)} R$`}
          detail={freightShare == null ? undefined : `${pct(freightShare)} so với doanh thu hàng`}
        />
    </div>
  )
}
