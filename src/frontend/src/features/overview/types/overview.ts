export type OverviewResponse = {
  sales: {
    product_sales: number
    freight_value: number
    items_sold: number
    orders: number
  }
  payment: {
    customers: number
    orders: number
    payment_value: number
    aov: number
  }
  customers: {
    one_time: number
    repeat_buyers: number
    vip: number
  }
  reconciliation: {
    price_plus_freight: number
    payment_minus_price_and_freight: number
  }
}
