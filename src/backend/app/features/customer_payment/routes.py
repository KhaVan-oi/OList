"""Màn Khách và thanh toán. Tiền chỉ tính trên đơn delivered."""

from flask import Blueprint, request

from app.common.http import ok, screen_endpoint
from app.common.params import limit_arg, state_arg, states_arg, year_arg
from app.common.query_gateway import QueryGateway

_DELIVERED_CUSTOMERS = """
FROM dw.fact_customer_order f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.order_status = 'delivered'
"""

_ORDER_STATUSES = (
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "created", "approved",
)

_LABELS = {
    "once": "Mua một lần",
    "repeat": "Mua lại",
    "t1": "1 đơn",
    "t2": "2 đơn",
    "t3": "3 đơn",
    "t4": "Từ 4 đơn",
}

_METRICS = """
    count(DISTINCT c.customer_unique_id) AS customers,
    count(f.order_id) AS orders,
    round(sum(coalesce(f.total_payment_value, 0)), 2) AS payment_value,
    round(avg(f.total_payment_value), 2) AS aov
"""

_ORDER_JOIN = """
FROM dw.fact_customer_order f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
"""


def _label_rows(rows):
    for row in rows:
        row["label"] = _LABELS.get(row["key"], row["key"])
    return rows


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
                    coalesce(f.total_payment_value, 0) AS payment_value,
                    f.total_payment_value AS raw_payment_value
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
                round(sum(o.payment_value), 2) AS payment_value,
                round(avg(o.raw_payment_value), 2) AS aov
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

    @screen.get("/drilldown")
    @screen_endpoint
    def drilldown():
        """Roll-up / drill-down theo ba chiều. Tổng của mỗi cấp được đếm lại, không cộng từ dòng con.

        dim=customer: tất cả -> nhóm (mua một lần / mua lại) -> bậc tần suất
        dim=geo:      toàn quốc -> bang -> 15 thành phố thanh toán cao nhất
        dim=status:   mọi trạng thái -> một trạng thái -> bang (tiền chỉ tính cho delivered)
        """
        dim = request.args.get("dim", "customer")
        if dim == "customer":
            return _drill_customer()
        if dim == "geo":
            return _drill_geo()
        if dim == "status":
            return _drill_status()
        raise ValueError("dim là customer, geo hoặc status")

    def _drill_customer():
        group = request.args.get("group", "")
        if group not in ("", "once", "repeat"):
            raise ValueError("group là once hoặc repeat")
        cte = f"""
            WITH cust AS (
                SELECT c.customer_unique_id,
                       count(*) AS orders,
                       count(f.total_payment_value) AS paid,
                       sum(coalesce(f.total_payment_value, 0)) AS spend
                {_DELIVERED_CUSTOMERS}
                GROUP BY c.customer_unique_id
            )
        """
        where = {"": "", "once": "WHERE orders = 1", "repeat": "WHERE orders >= 2"}[group]
        key = (
            "CASE WHEN orders = 1 THEN 'once' ELSE 'repeat' END"
            if not group
            else "CASE WHEN orders = 1 THEN 't1' WHEN orders = 2 THEN 't2' WHEN orders = 3 THEN 't3' ELSE 't4' END"
        )
        measures = """
            count(*) AS customers,
            sum(orders)::bigint AS orders,
            round(sum(spend), 2) AS payment_value,
            round(sum(spend) / nullif(sum(paid), 0), 2) AS aov
        """
        rows = gateway.fetch_all(
            f"{cte} SELECT {key} AS key, {measures} FROM cust {where} GROUP BY 1 ORDER BY min(orders)"
        )
        total = gateway.fetch_one(f"{cte} SELECT {measures} FROM cust {where}")
        return ok(
            "customer_payment", dim="customer", group=group or None,
            level=1 if group else 0, data=_label_rows(rows), total=total,
            note="Mỗi khách đếm một lần theo số đơn delivered.",
        )

    def _drill_geo():
        state = (request.args.get("state") or "").strip().upper()
        base = f"""
            SELECT {{select}}, {_METRICS}
            {_ORDER_JOIN}
            WHERE f.order_status = 'delivered' AND f.customer_state IS NOT NULL
        """
        if not state:
            rows = gateway.fetch_all(
                base.format(select="f.customer_state AS key")
                + " GROUP BY f.customer_state ORDER BY sum(coalesce(f.total_payment_value, 0)) DESC, f.customer_state"
            )
            total = gateway.fetch_one(base.format(select="'ALL' AS key"))
            level = 0
        else:
            state = state_arg()
            rows = gateway.fetch_all(
                base.format(select="f.customer_city AS key")
                + " AND f.customer_state = %s AND f.customer_city IS NOT NULL"
                + " GROUP BY f.customer_city"
                + " ORDER BY sum(coalesce(f.total_payment_value, 0)) DESC, count(f.order_id) DESC, f.customer_city"
                + " LIMIT 15",
                (state,),
            )
            total = gateway.fetch_one(base.format(select="'ALL' AS key") + " AND f.customer_state = %s", (state,))
            level = 1
        return ok(
            "customer_payment", dim="geo", state=state or None, level=level,
            data=_label_rows(rows), total=total,
            note="Khách đếm theo bang/thành phố của đơn, nên tổng các dòng có thể lớn hơn tổng đã đếm lại.",
        )

    def _drill_status():
        status = (request.args.get("status") or "").strip()
        if status and status not in _ORDER_STATUSES:
            raise ValueError("status không hợp lệ")
        metrics = """
            count(DISTINCT c.customer_unique_id) AS customers,
            count(f.order_id) AS orders,
            round(sum(coalesce(f.total_payment_value, 0)) FILTER (WHERE f.order_status = 'delivered'), 2) AS payment_value,
            round(avg(f.total_payment_value) FILTER (WHERE f.order_status = 'delivered'), 2) AS aov
        """
        base = f"SELECT {{select}}, {metrics} {_ORDER_JOIN}"
        if not status:
            rows = gateway.fetch_all(
                base.format(select="f.order_status AS key")
                + " GROUP BY f.order_status ORDER BY count(f.order_id) DESC, f.order_status"
            )
            total = gateway.fetch_one(base.format(select="'ALL' AS key"))
            level = 0
        else:
            rows = gateway.fetch_all(
                base.format(select="f.customer_state AS key")
                + " WHERE f.order_status = %s AND f.customer_state IS NOT NULL"
                + " GROUP BY f.customer_state ORDER BY count(f.order_id) DESC, f.customer_state",
                (status,),
            )
            total = gateway.fetch_one(
                base.format(select="'ALL' AS key") + " WHERE f.order_status = %s", (status,)
            )
            level = 1
        return ok(
            "customer_payment", dim="status", status=status or None, level=level,
            data=_label_rows(rows), total=total,
            note="Tiền chỉ tính cho đơn delivered; trạng thái khác để trống.",
        )

    @screen.get("/matrix")
    @screen_endpoint
    def matrix_state_year():
        """Bang × Năm cho mọi khách delivered. states rỗng = tất cả bang."""
        states = states_arg(())
        year_from = year_arg("year_from", 2016)
        year_to = year_arg("year_to", 2018)
        if year_from > year_to:
            raise ValueError("year_from không lớn hơn year_to")
        data = gateway.fetch_all(
            f"""
            SELECT
                f.customer_state,
                d.year,
                {_METRICS}
            {_ORDER_JOIN}
            JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
            WHERE f.order_status = 'delivered'
              AND f.customer_state IS NOT NULL
              AND (cardinality(%s::text[]) = 0 OR f.customer_state = ANY(%s))
              AND d.year BETWEEN %s AND %s
            GROUP BY f.customer_state, d.year
            ORDER BY f.customer_state, d.year
            """,
            (states, states, year_from, year_to),
        )
        return ok(
            "customer_payment", states=states, year_from=year_from, year_to=year_to, data=data,
            note="Khách đếm riêng từng ô, không cộng giữa các ô.",
        )

    @screen.get("/ranking")
    @screen_endpoint
    def rank_spenders():
        """Top 3 khách chi nhiều nhất trong từng bang (DENSE_RANK) và phân vị chi tiêu toàn quốc (PERCENT_RANK)."""
        selected_states = states_arg(("SP", "RJ", "MG", "RS", "PR"))
        data = gateway.fetch_all(
            f"""
            WITH national AS (
                SELECT c.customer_unique_id,
                       round(sum(coalesce(f.total_payment_value, 0)), 2) AS national_total_spend
                {_DELIVERED_CUSTOMERS}
                GROUP BY c.customer_unique_id
            ),
            percentile AS (
                SELECT customer_unique_id,
                       round((percent_rank() OVER (ORDER BY national_total_spend ASC) * 100)::numeric, 2)
                           AS national_spend_percentile
                FROM national
            ),
            state_spend AS (
                SELECT c.customer_unique_id, f.customer_state,
                       count(*) AS state_orders,
                       round(sum(coalesce(f.total_payment_value, 0)), 2) AS state_spend
                {_DELIVERED_CUSTOMERS}
                  AND f.customer_state = ANY(%s)
                GROUP BY c.customer_unique_id, f.customer_state
            ),
            ranked AS (
                SELECT s.*, p.national_spend_percentile,
                       dense_rank() OVER (PARTITION BY s.customer_state ORDER BY s.state_spend DESC)
                           AS state_spend_rank,
                       row_number() OVER (
                           PARTITION BY s.customer_state
                           ORDER BY s.state_spend DESC, s.state_orders DESC, s.customer_unique_id ASC
                       ) AS rn
                FROM state_spend s
                JOIN percentile p ON p.customer_unique_id = s.customer_unique_id
            )
            SELECT customer_state, state_spend_rank, trim(customer_unique_id) AS customer_unique_id,
                   state_orders, state_spend, national_spend_percentile
            FROM ranked
            WHERE rn <= 3
            ORDER BY customer_state, rn
            """,
            (selected_states,),
        )
        return ok(
            "customer_payment", states=selected_states, data=data,
            note="Hạng trong bang: cùng số tiền thì cùng hạng. Phân vị so với mọi khách delivered toàn quốc.",
        )

    return screen
