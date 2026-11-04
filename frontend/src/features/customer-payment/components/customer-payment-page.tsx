import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeading } from '../../../components/layouts'
import { QueryState } from '../../../components/ui'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table.tsx'
import { chartGrid, chartSales, chartTick } from '../../../lib/chart.ts'
import { count, money, pct } from '../../../lib/format.ts'
import type { Row } from '../../../types/api.ts'
import { getOverview } from '../../overview/services/overviewApi.ts'
import { getFrequency } from '../services/customerPaymentApi.ts'

const tick = { fill: chartTick, fontSize: 12 }

export function CustomerPaymentPage() {
  const frequency = useQuery({ queryKey: ['customer-payment', 'frequency'], queryFn: getFrequency })
  const overview = useQuery({ queryKey: ['overview'], queryFn: getOverview })
  const customers = overview.data?.customers
  const total = customers ? customers.one_time + customers.repeat_buyers : 0
  const repeatRate = total ? (customers!.repeat_buyers / total) * 100 : null
  const rows = frequency.data?.data ?? []

  return (
    <section className="space-y-4">
      <PageHeading
        title="Khách hàng"
        description="Khách delivered, bậc tần suất và khách chi trên 1.000 R$."
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
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Bậc tần suất</CardTitle>
            <CardDescription>Mỗi khách đếm một lần theo số đơn delivered.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <QueryState loading={frequency.isLoading} error={frequency.error}>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows.map(shortTier)}>
                  <CartesianGrid vertical={false} stroke={chartGrid} />
                  <XAxis dataKey="label" tick={tick} />
                  <YAxis tickFormatter={(value) => count(Number(value))} width={48} tick={tick} />
                  <Tooltip formatter={(value) => count(typeof value === 'number' ? value : Number(value))} />
                  <Bar dataKey="customers" name="Khách" fill={chartSales} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Bậc tần suất</TableHead>
                  <TableHead className="text-right">Khách</TableHead>
                  <TableHead className="text-right">Thanh toán</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={String(row.frequency_tier)}>
                    <TableCell>{shortTier(row).label}</TableCell>
                    <TableCell className="text-right tabular-nums">{count(Number(row.customers))}</TableCell>
                    <TableCell className="text-right tabular-nums">{money(Number(row.payment_value))}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </QueryState>
        </CardContent>
      </Card>
    </section>
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
