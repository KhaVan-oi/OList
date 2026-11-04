"""Màn Khách và thanh toán. Tiền chỉ tính trên đơn delivered."""

from flask import Blueprint

from app.common.http import ok, screen_endpoint
from app.common.params import limit_arg, states_arg, year_arg
from app.common.query_gateway import QueryGateway

_DELIVERED_CUSTOMERS = """
FROM dw.fact_customer_order f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.order_status = 'delivered'
"""


def create_customer_payment_blueprint(gateway: QueryGateway):
    screen = Blueprint(
        "customer_payment_screen",
        __name__,
        url_prefix="/api/customer-payment",
    )

    @screen.get("/frequency")
    @screen_endpoint
    def list_frequency_tiers():
        data = gateway.fetch_all(
            f"""
            WITH cust AS (
                SELECT c.customer_unique_id, count(*) AS orders,
                       sum(coalesce(f.total_payment_value, 0)) AS spend
                {_DELIVERED_CUSTOMERS}
                GROUP BY c.customer_unique_id
            )
            SELECT
                CASE
                    WHEN orders = 1 THEN '1.1. Mua dung 1 don'
                    WHEN orders = 2 THEN '2.1. Mua 2 don'
                    WHEN orders = 3 THEN '2.2. Mua 3 don'
                    ELSE '2.3. Mua tu 4 don tro len'
                END AS frequency_tier,
                count(*) AS customers,
                round(sum(spend), 2) AS payment_value
            FROM cust
            GROUP BY 1
            ORDER BY min(orders)
            """
        )
        return ok("customer_payment", data=data)

    @screen.get("/states")
    @screen_endpoint
    def list_states():
        data = gateway.fetch_all(
            f"""
            SELECT
                f.customer_state,
                count(DISTINCT c.customer_unique_id) AS customers,
                count(f.order_id) AS orders,
                round(sum(coalesce(f.total_payment_value, 0)), 2) AS payment_value,
                round(avg(f.total_payment_value), 2) AS aov
            {_DELIVERED_CUSTOMERS}
              AND f.customer_state IS NOT NULL
            GROUP BY f.customer_state
            ORDER BY sum(coalesce(f.total_payment_value, 0)) DESC, f.customer_state
            """
        )
        return ok("customer_payment", data=data)

    @screen.get("/statuses")
    @screen_endpoint
    def list_order_statuses():
        data = gateway.fetch_all(
            """
            SELECT
                order_status,
                count(*) AS orders,
                round(100.0 * count(*) / nullif(sum(count(*)) OVER (), 0), 2) AS pct
            FROM dw.fact_customer_order
            GROUP BY order_status
            ORDER BY count(*) DESC, order_status
            """
        )
        return ok(
            "customer_payment",
            data=data,
            note="Mọi trạng thái. Tiền không lấy từ endpoint này.",
        )

    @screen.get("/vip")
    @screen_endpoint
    def list_vip_customers():
        data = gateway.fetch_all(
            f"""
            WITH cust AS (
                SELECT
                    trim(c.customer_unique_id) AS customer_unique_id,
                    count(*) AS orders,
                    sum(coalesce(f.total_payment_value, 0)) AS payment_value
                {_DELIVERED_CUSTOMERS}
                GROUP BY c.customer_unique_id
            )
            SELECT customer_unique_id, orders, round(payment_value, 2) AS payment_value
            FROM cust
            WHERE payment_value > 1000
            ORDER BY payment_value DESC, customer_unique_id
            LIMIT %s
            """,
            (limit_arg(default=20),),
        )
        return ok("customer_payment", data=data, rule="payment_value > 1000")

    @screen.get("/cube")
    @screen_endpoint
    def cube_state_year():
        selected_states = states_arg(("SP", "RJ", "MG", "RS", "PR"))
        years = [year_arg("year_from", 2017), year_arg("year_to", 2018)]
        data = gateway.fetch_all(
            """
            SELECT
                d.year,
                f.customer_state,
                count(DISTINCT c.customer_unique_id) AS customers,
                count(f.order_id) AS orders,
                round(sum(coalesce(f.total_payment_value, 0)), 2) AS payment_value
            FROM dw.fact_customer_order f
            JOIN dw.dim_customer c ON c.customer_key = f.customer_key
            JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
            WHERE f.order_status = 'delivered'
              AND f.customer_state = ANY(%s)
              AND d.year = ANY(%s)
            GROUP BY d.year, f.customer_state
            ORDER BY d.year, f.customer_state
            """,
            (selected_states, years),
        )
        return ok("customer_payment", states=selected_states, years=years, data=data)

    @screen.get("/dice")
    @screen_endpoint
    def dice_repeat_buyers():
        selected_states = states_arg(("SP", "RJ", "MG"))
        year_from = year_arg("year_from", 2017)
        year_to = year_arg("year_to", 2018)
        if year_from > year_to:
            raise ValueError("year_from không lớn hơn year_to")
        data = gateway.fetch_all(
            """
            WITH orders_in_scope AS (
                SELECT
                    c.customer_unique_id,
                    f.customer_state,
                    d.year,
                    f.order_id,
                    coalesce(f.total_payment_value, 0) AS payment_value
                FROM dw.fact_customer_order f
                JOIN dw.dim_customer c ON c.customer_key = f.customer_key
                JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
                WHERE f.order_status = 'delivered'
                  AND f.customer_state = ANY(%s)
                  AND d.year BETWEEN %s AND %s
            ),
            repeaters AS (
                SELECT customer_unique_id
                FROM orders_in_scope
                GROUP BY customer_unique_id
                HAVING count(*) >= 2
            )
            SELECT
                o.customer_state,
                o.year,
                count(DISTINCT o.customer_unique_id) AS customers,
                count(o.order_id) AS orders,
                round(sum(o.payment_value), 2) AS payment_value
            FROM orders_in_scope o
            JOIN repeaters r ON r.customer_unique_id = o.customer_unique_id
            GROUP BY o.customer_state, o.year
            ORDER BY o.year, o.customer_state
            """,
            (selected_states, year_from, year_to),
        )
        return ok(
            "customer_payment",
            states=selected_states,
            year_from=year_from,
            year_to=year_to,
            data=data,
            note="Khách có ít nhất 2 đơn delivered trong phạm vi bang và năm. Không cộng customers xuyên bang.",
        )

    return screen
