"""Màn Tổng quan: ba thước đo tiền đứng riêng, kèm bước đối soát."""

from flask import Blueprint

from app.common.http import ok, screen_endpoint
from app.common.query_gateway import QueryGateway

_SALES = """
SELECT
    round(sum(fs.price), 2) AS product_sales,
    round(sum(fs.freight_value), 2) AS freight_value,
    count(*) AS items_sold,
    count(DISTINCT fs.order_id) AS orders
FROM dw.fact_sales fs
JOIN dw.fact_customer_order fco ON fco.order_id = fs.order_id
WHERE fco.order_status = 'delivered'
"""

_PAYMENT = """
SELECT
    count(DISTINCT c.customer_unique_id) AS customers,
    count(f.order_id) AS orders,
    round(sum(coalesce(f.total_payment_value, 0)), 2) AS payment_value,
    round(avg(f.total_payment_value), 2) AS aov
FROM dw.fact_customer_order f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.order_status = 'delivered'
"""

_CUSTOMERS = """
WITH cust AS (
    SELECT
        c.customer_unique_id,
        count(*) AS orders,
        sum(coalesce(f.total_payment_value, 0)) AS spend
    FROM dw.fact_customer_order f
    JOIN dw.dim_customer c ON c.customer_key = f.customer_key
    WHERE f.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT
    count(*) FILTER (WHERE orders = 1) AS one_time,
    count(*) FILTER (WHERE orders >= 2) AS repeat_buyers,
    count(*) FILTER (WHERE spend > 1000) AS vip
FROM cust
"""


def create_overview_blueprint(gateway: QueryGateway):
    screen = Blueprint("overview_screen", __name__, url_prefix="/api/overview")

    @screen.get("")
    @screen_endpoint
    def get_overview():
        sales = gateway.fetch_one(_SALES)
        payment = gateway.fetch_one(_PAYMENT)
        customers = gateway.fetch_one(_CUSTOMERS)
        price_plus_freight = round(sales["product_sales"] + sales["freight_value"], 2)
        return ok(
            "overview",
            sales=sales,
            payment=payment,
            customers=customers,
            reconciliation={
                "price_plus_freight": price_plus_freight,
                "payment_minus_price_and_freight": round(
                    payment["payment_value"] - price_plus_freight, 2
                ),
            },
        )

    return screen
