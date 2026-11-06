"""Hàng hóa và địa lý. Route validate + QueryGateway; SQL không mở conn trong handler."""

import re

from flask import Blueprint, jsonify, request

from app.common.query_gateway import QueryGateway

_SELLER = re.compile(r"^[0-9a-fA-F]{32}$")
_STATE = re.compile(r"^[A-Z]{2}$")


def _limit(default, maximum=50):
    raw = request.args.get("limit")
    if raw is None or raw == "":
        return default, None
    try:
        value = int(raw)
    except ValueError:
        return None, f"limit là số từ 1 đến {maximum}"
    if not 1 <= value <= maximum:
        return None, f"limit là số từ 1 đến {maximum}"
    return value, None


def _period():
    """Lát thời gian optional: year, quarter (quarter bắt buộc kèm year)."""
    year_raw = request.args.get("year")
    quarter_raw = request.args.get("quarter")
    year = None
    quarter = None
    if year_raw not in (None, ""):
        try:
            year = int(year_raw)
        except ValueError:
            return None, None, "year là số (2016-2018)"
        if year < 2016 or year > 2018:
            return None, None, "year trong 2016-2018"
    if quarter_raw not in (None, ""):
        try:
            quarter = int(quarter_raw)
        except ValueError:
            return None, None, "quarter là 1-4"
        if quarter not in (1, 2, 3, 4):
            return None, None, "quarter là 1-4"
        if year is None:
            return None, None, "quarter cần kèm year"
    return year, quarter, None


def _valid_sales(year=None, quarter=None):
    """Nền delivered + dim_date. Lát năm/quý nằm trong CTE để top/dice cùng kỳ."""
    clauses = ["o.order_status = 'delivered'"]
    params = []
    if year is not None:
        clauses.append("d.year = %s")
        params.append(year)
    if quarter is not None:
        clauses.append("d.quarter = %s")
        params.append(quarter)
    sql = f"""
valid_sales AS (
    SELECT
        s.order_id,
        s.price,
        s.freight_value,
        trim(p.product_id) AS product_id,
        coalesce(p.product_category_name_english, p.product_category_name, 'Unknown') AS category,
        trim(sel.seller_id) AS seller_id,
        o.customer_state,
        o.customer_city,
        d.year,
        d.quarter,
        d.month
    FROM dw.fact_sales AS s
    JOIN dw.fact_customer_order AS o ON o.order_id = s.order_id
    JOIN dw.dim_product AS p ON p.product_key = s.product_key
    JOIN dw.dim_seller AS sel ON sel.seller_key = s.seller_key
    JOIN dw.dim_date AS d ON d.date_key = s.purchase_date_key
    WHERE {" AND ".join(clauses)}
)
"""
    return sql, tuple(params)


def _categories(default):
    raw = request.args.get("categories") or request.args.get("category")
    if raw is None or raw.strip() == "":
        return list(default), None
    items = [part.strip() for part in raw.split(",") if part.strip()]
    if not items or any(len(item) > 100 for item in items):
        return None, "category là tên danh mục, cách nhau bởi dấu phẩy"
    return items, None


def _states(default):
    raw = request.args.get("states")
    if raw is None or raw.strip() == "":
        return list(default), None
    states = [part.strip().upper() for part in raw.split(",") if part.strip()]
    if not states or any(_STATE.match(state) is None for state in states):
        return None, "states là mã bang 2 chữ, cách nhau bởi dấu phẩy"
    return states, None


def _state():
    raw = (request.args.get("state") or "").strip().upper()
    if raw and _STATE.match(raw) is None:
        return None, "state là mã bang 2 chữ"
    return raw, None


def _optional_category():
    raw = (request.args.get("category") or "").strip()
    if len(raw) > 100:
        return None, "category là tên danh mục"
    return raw, None


def _optional_states():
    """Rỗng = không lát bang. Có giá trị = lọc đúng các bang (xếp hạng)."""
    raw = request.args.get("states")
    if raw is None or raw.strip() == "":
        return [], None
    states = [part.strip().upper() for part in raw.split(",") if part.strip()]
    if not states or any(_STATE.match(state) is None for state in states):
        return None, "states là mã bang 2 chữ, cách nhau bởi dấu phẩy"
    return states, None


def _sellers():
    raw = request.args.get("sellers")
    if raw is None or raw.strip() == "":
        return None, None
    sellers = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not sellers or any(_SELLER.match(seller) is None for seller in sellers):
        return None, "sellers là seller_id 32 ký tự hex, cách nhau bởi dấu phẩy"
    return sellers, None


def _ok(operation, data, **extra):
    return jsonify({"status": "ok", "operation": operation, "data": data, **extra})


class _ValidSalesFormat:
    """Cho phép f"WITH {_VALID_SALES}" vẫn áp lát year/quarter từ request."""

    params = ()
    year = None
    quarter = None

    def __format__(self, format_spec):
        year, quarter, error = _period()
        if error:
            raise ValueError(error)
        cte, params = _valid_sales(year, quarter)
        type(self).params = params
        type(self).year = year
        type(self).quarter = quarter
        return cte


_VALID_SALES = _ValidSalesFormat()


def _period_params(*extra):
    return _ValidSalesFormat.params + tuple(extra)


def _period_fields():
    return {"year": _ValidSalesFormat.year, "quarter": _ValidSalesFormat.quarter}



def create_product_geo_blueprint(gateway: QueryGateway):
    bp = Blueprint("product_geo", __name__)

    @bp.route("/api/product-geo/periods", methods=["GET"])
    def product_periods():
        """Các năm/quý có đơn delivered — dùng cho filter lát thời gian."""
        try:
            data = gateway.fetch_all(
                """
                SELECT
                    d.year,
                    d.quarter,
                    count(*) AS items_sold,
                    count(DISTINCT s.order_id) AS orders
                FROM dw.fact_sales AS s
                JOIN dw.fact_customer_order AS o ON o.order_id = s.order_id
                JOIN dw.dim_date AS d ON d.date_key = s.purchase_date_key
                WHERE o.order_status = 'delivered'
                GROUP BY d.year, d.quarter
                ORDER BY d.year, d.quarter
                """
            )
            years = sorted({row["year"] for row in data if isinstance(row.get("year"), int)})
            return _ok("periods", data, years=years, note="Lát thời gian trên OLAP hàng hóa/seller. Quý luôn kèm năm.")
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/summary", methods=["GET"])
    def product_summary():
        """0. Tổng doanh thu hàng, cước, số món, số đơn. category lọc cả bốn số."""
        category, error = _optional_category()
        if error:
            return jsonify({"error": error}), 400
        year, quarter, error = _period()
        if error:
            return jsonify({"error": error}), 400
        cte, period_params = _valid_sales(year, quarter)
        try:
            data = gateway.fetch_all(
                f"""
                WITH {cte}
                SELECT
                    round(sum(price), 2) AS total_revenue,
                    round(sum(freight_value), 2) AS total_freight,
                    round(sum(freight_value) / nullif(sum(price), 0), 4) AS freight_to_price_ratio,
                    count(*) AS items_sold,
                    count(DISTINCT order_id) AS orders_with_items
                FROM valid_sales
                WHERE (%s = '' OR category = %s)
                """,
                period_params + (category, category),
            )
            return _ok("summary", data, category=category or None, year=year, quarter=quarter)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/categories", methods=["GET"])
    def product_categories():
        """1. Danh mục theo doanh thu. Mặc định 10, tối đa 200 để phân trang FE."""
        limit, error = _limit(10, maximum=200)
        if error:
            return jsonify({"error": error}), 400
        year, quarter, error = _period()
        if error:
            return jsonify({"error": error}), 400
        cte, period_params = _valid_sales(year, quarter)
        try:
            data = gateway.fetch_all(
                f"""
                WITH {cte}
                SELECT
                    category,
                    round(sum(price), 2) AS revenue,
                    count(*) AS items_sold,
                    count(DISTINCT order_id) AS orders
                FROM valid_sales
                GROUP BY category
                ORDER BY sum(price) DESC, count(*) DESC, category
                LIMIT %s
                """,
                period_params + (limit,),
            )
            return _ok(
                "categories",
                data,
                year=year,
                quarter=quarter,
                note="orders đúng trên từng danh mục. Không cộng cột orders giữa các danh mục.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/sellers", methods=["GET"])
    def product_sellers():
        """2. Top seller. Mặc định 10. Top tính trong kỳ lát nếu có year/quarter. states = lát bang (không phải dice)."""
        limit, error = _limit(10)
        if error:
            return jsonify({"error": error}), 400
        category, error = _optional_category()
        if error:
            return jsonify({"error": error}), 400
        states, error = _optional_states()
        if error:
            return jsonify({"error": error}), 400
        year, quarter, error = _period()
        if error:
            return jsonify({"error": error}), 400
        cte, period_params = _valid_sales(year, quarter)
        try:
            data = gateway.fetch_all(
                f"""
                WITH {cte}
                SELECT
                    seller_id,
                    round(sum(price), 2) AS revenue,
                    count(*) AS items_sold,
                    count(DISTINCT order_id) AS orders
                FROM valid_sales
                WHERE (%s = '' OR category = %s)
                  AND (cardinality(%s::text[]) = 0 OR customer_state = ANY(%s))
                GROUP BY seller_id
                ORDER BY sum(price) DESC, count(*) DESC, seller_id
                LIMIT %s
                """,
                period_params + (category, category, states, states, limit),
            )
            return _ok(
                "sellers",
                data,
                category=category or None,
                states=states or None,
                year=year,
                quarter=quarter,
                note="Một đơn có thể có nhiều seller. Không cộng cột orders giữa các seller.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/pareto", methods=["GET"])
    def product_pareto():
        """3. Pareto 20% mã. Không category: tóm tắt + danh mục. Có category: khoan xuống mã trong nhóm 20%."""
        category, error = _optional_category()
        if error:
            return jsonify({"error": error}), 400
        limit, error = _limit(12)
        if error:
            return jsonify({"error": error}), 400
        try:
            cutoff_cte = f"""
                WITH {_VALID_SALES},
                product_rev AS (
                    SELECT product_id, category, sum(price) AS revenue, count(*) AS items_sold
                    FROM valid_sales
                    GROUP BY product_id, category
                ),
                ranked AS (
                    SELECT
                        product_id,
                        category,
                        revenue,
                        row_number() OVER (
                            ORDER BY revenue DESC, items_sold DESC, product_id
                        ) AS rn,
                        count(*) OVER () AS n_products,
                        sum(revenue) OVER () AS total_revenue
                    FROM product_rev
                ),
                cutoff AS (
                    SELECT *
                    FROM ranked
                    WHERE rn <= ceil(n_products * 0.20)
                )
            """
            if category:
                products_sql = f"""
                    {cutoff_cte}
                    SELECT
                        product_id,
                        category,
                        rn AS rank_in_pareto,
                        round(revenue, 2) AS revenue,
                        round(
                            100.0 * revenue / nullif(sum(revenue) OVER (), 0),
                            2
                        ) AS pct_of_category_top
                    FROM cutoff
                    WHERE category = %s
                    ORDER BY revenue DESC, product_id
                    LIMIT %s
                """
                data = gateway.fetch_all(products_sql, _period_params(category, limit))
                return _ok(
                    "pareto",
                    data,
                    category=category,
                    limit=limit,
                    **_period_fields(),
                    note="Khoan Pareto: mã thuộc top 20% toàn kho và nằm trong danh mục đã chọn. Cuộn về danh mục bằng cách bỏ category.",
                )

            summary_sql = f"""
                {cutoff_cte}
                SELECT
                    max(n_products) AS n_products,
                    count(*) AS n_top_20pct_products,
                    round(max(total_revenue), 2) AS total_revenue,
                    round(sum(revenue), 2) AS top_20pct_revenue,
                    round(100.0 * sum(revenue) / nullif(max(total_revenue), 0), 2) AS pct_of_total_revenue
                FROM cutoff
            """
            categories_sql = f"""
                {cutoff_cte}
                SELECT
                    category,
                    count(*) AS n_products,
                    round(sum(revenue), 2) AS revenue,
                    round(
                        100.0 * sum(revenue) / nullif(sum(sum(revenue)) OVER (), 0),
                        2
                    ) AS pct_of_top_revenue
                FROM cutoff
                GROUP BY category
                ORDER BY sum(revenue) DESC, category
                LIMIT 8
            """
            data = gateway.fetch_all(summary_sql, _period_params())
            categories = gateway.fetch_all(categories_sql, _period_params())
            return _ok(
                "pareto",
                data,
                categories=categories,
                **_period_fields(),
                note="Mã chỉ là product_id (hash). Pareto đếm theo id rồi gom nhóm 20% theo danh mục để đọc được.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/freight", methods=["GET"])
    def product_freight():
        """4. Tỷ lệ cước trên giá bán."""
        try:
            data = gateway.fetch_all(
                f"""
                WITH {_VALID_SALES}
                SELECT
                    round(sum(freight_value), 2) AS total_freight,
                    round(sum(price), 2) AS total_revenue,
                    round(sum(freight_value) / nullif(sum(price), 0), 4) AS freight_to_price_ratio
                FROM valid_sales
                """
                ,
                _period_params(),
            )
            return _ok("freight", data, **_period_fields())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/states", methods=["GET"])
    def product_states():
        """5. Doanh thu và số đơn theo bang. Cộng orders theo bang thì được."""
        category, error = _optional_category()
        if error:
            return jsonify({"error": error}), 400
        try:
            data = gateway.fetch_all(
                f"""
                WITH {_VALID_SALES}
                SELECT
                    customer_state,
                    count(DISTINCT order_id) AS orders,
                    round(sum(price), 2) AS revenue,
                    round(sum(freight_value), 2) AS freight,
                    count(*) AS items_sold
                FROM valid_sales
                WHERE (%s = '' OR category = %s)
                GROUP BY customer_state
                ORDER BY sum(price) DESC, count(*) DESC, customer_state
                """,
                _period_params(category, category),
            )
            return _ok(
                "states",
                data,
                category=category or None,
                **_period_fields(),
                note="Mỗi đơn một bang, nên cộng orders theo bang thì được.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/rollup", methods=["GET"])
    def product_rollup():
        """6. ROLLUP thành phố → bang → toàn bộ. orders được tính lại ở mỗi mức."""
        level = request.args.get("level", "all")
        if level not in ("all", "state", "city", "grand"):
            return jsonify({"error": "level phải là all, grand, state hoặc city"}), 400
        having = {
            "all": "",
            "grand": "HAVING grouping(customer_state) = 1",
            "state": "HAVING grouping(customer_state) = 0 AND grouping(customer_city) = 1",
            "city": "HAVING grouping(customer_city) = 0",
        }[level]
        try:
            data = gateway.fetch_all(
                f"""
                WITH {_VALID_SALES}
                SELECT
                    CASE
                        WHEN grouping(customer_state) = 1 THEN '(ALL STATES)'
                        ELSE coalesce(customer_state, '(NULL STATE)')
                    END AS customer_state,
                    CASE
                        WHEN grouping(customer_city) = 1 THEN '(ALL CITIES)'
                        ELSE coalesce(customer_city, '(NULL CITY)')
                    END AS customer_city,
                    grouping(customer_state) AS grouping_state,
                    grouping(customer_city) AS grouping_city,
                    round(sum(price), 2) AS revenue,
                    count(DISTINCT order_id) AS orders,
                    count(*) AS items_sold
                FROM valid_sales
                GROUP BY ROLLUP (customer_state, customer_city)
                {having}
                ORDER BY
                    grouping(customer_state),
                    sum(price) DESC,
                    customer_state,
                    grouping(customer_city),
                    customer_city
                """,
                _period_params(),
            )
            return _ok(
                "rollup",
                data,
                level=level,
                **_period_fields(),
                note="grouping_state hoặc grouping_city = 1 là dòng tổng. orders được đếm lại, không cộng từ dòng con.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/drilldown", methods=["GET"])
    def product_drilldown():
        """7. Khoan địa lý: toàn bộ → bang → thành phố của một bang.

        Không có tham số: một dòng toàn bộ.
        level=state: các bang.
        state=SP: thành phố của bang đó. Đây là lá, không khoan thêm.
        level=city: thành phố của mọi bang.
        """
        level = request.args.get("level", "all")
        state, error = _state()
        if error:
            return jsonify({"error": error}), 400
        category, error = _optional_category()
        if error:
            return jsonify({"error": error}), 400
        if level not in ("all", "state", "city"):
            return jsonify({"error": "level phải là all, state hoặc city"}), 400
        if state:
            level = "city"
        try:
            if level == "all" and not state:
                data = gateway.fetch_all(
                    f"""
                    WITH {_VALID_SALES}
                    SELECT
                        '(ALL)' AS geo_level,
                        round(sum(price), 2) AS revenue,
                        round(sum(freight_value), 2) AS freight,
                        count(*) AS items_sold,
                        count(DISTINCT order_id) AS orders
                    FROM valid_sales
                    WHERE (%s = '' OR category = %s)
                    """,
                    _period_params(category, category),
                )
            elif level == "state":
                data = gateway.fetch_all(
                    f"""
                    WITH {_VALID_SALES}
                    SELECT
                        customer_state,
                        round(sum(price), 2) AS revenue,
                        round(sum(freight_value), 2) AS freight,
                        count(*) AS items_sold,
                        count(DISTINCT order_id) AS orders
                    FROM valid_sales
                    WHERE customer_state IS NOT NULL
                      AND (%s = '' OR category = %s)
                    GROUP BY customer_state
                    ORDER BY sum(price) DESC, count(*) DESC, customer_state
                    """,
                    _period_params(category, category),
                )
            else:
                data = gateway.fetch_all(
                    f"""
                    WITH {_VALID_SALES}
                    SELECT
                        customer_state,
                        coalesce(customer_city, '(NULL CITY)') AS customer_city,
                        round(sum(price), 2) AS revenue,
                        round(sum(freight_value), 2) AS freight,
                        count(*) AS items_sold,
                        count(DISTINCT order_id) AS orders
                    FROM valid_sales
                    WHERE customer_state IS NOT NULL
                      AND (%s = '' OR customer_state = %s)
                      AND (%s = '' OR category = %s)
                    GROUP BY customer_state, customer_city
                    ORDER BY customer_state, sum(price) DESC, count(*) DESC, customer_city
                    """,
                    _period_params(state, state, category, category),
                )
            return _ok(
                "drilldown",
                data,
                level="city" if state else level,
                state=state or None,
                category=category or None,
                **_period_fields(),
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/slice", methods=["GET"])
    def product_slice():
        """8. Cố định danh mục, xem theo bang. Mặc định health_beauty."""
        categories, error = _categories(("health_beauty",))
        if error:
            return jsonify({"error": error}), 400
        try:
            data = gateway.fetch_all(
                f"""
                WITH {_VALID_SALES}
                SELECT
                    category,
                    customer_state,
                    round(sum(price), 2) AS revenue,
                    count(*) AS items_sold,
                    count(DISTINCT order_id) AS orders
                FROM valid_sales
                WHERE category = ANY(%s)
                GROUP BY category, customer_state
                ORDER BY category, sum(price) DESC, count(*) DESC, customer_state
                """,
                _period_params(categories),
            )
            return _ok(
                "slice",
                data,
                categories=categories,
                **_period_fields(),
                note="Trong một danh mục, cộng orders theo bang được vì mỗi đơn chỉ một bang.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/dice", methods=["GET"])
    def product_dice():
        """9. Giao top seller ∩ một/nhiều bang ∩ một/nhiều danh mục. Không xếp hạng lại trong khối."""
        categories, error = _categories(("health_beauty",))
        if error:
            return jsonify({"error": error}), 400
        states, error = _states(("SP", "RJ", "MG"))
        if error:
            return jsonify({"error": error}), 400
        sellers, error = _sellers()
        if error:
            return jsonify({"error": error}), 400
        limit, error = _limit(10)
        if error:
            return jsonify({"error": error}), 400
        seller_filter = "seller_id = ANY(%s)" if sellers is not None else """
            seller_id IN (
                SELECT seller_id
                FROM valid_sales
                GROUP BY seller_id
                ORDER BY sum(price) DESC, count(*) DESC, seller_id
                LIMIT %s
            )
        """
        base = (sellers, states, categories) if sellers is not None else (limit, states, categories)
        try:
            data = gateway.fetch_all(
                f"""
                WITH {_VALID_SALES}
                SELECT
                    seller_id,
                    customer_state,
                    category,
                    round(sum(price), 2) AS revenue,
                    count(*) AS items_sold,
                    count(DISTINCT order_id) AS orders
                FROM valid_sales
                WHERE {seller_filter}
                  AND customer_state = ANY(%s)
                  AND category = ANY(%s)
                GROUP BY seller_id, customer_state, category
                ORDER BY category, sum(price) DESC, count(*) DESC, seller_id, customer_state
                """,
                _period_params(*base),
            )
            return _ok(
                "dice",
                data,
                categories=categories,
                states=states,
                sellers=sellers or f"top {limit} toàn kỳ",
                **_period_fields(),
                note="Seller không có doanh thu trong khối này không hiện. Top N và khối cùng kỳ lát. Không cộng orders giữa các seller.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo/rank", methods=["GET"])
    def product_rank():
        """10. Top danh mục trong từng bang. rn là hạng trong bang. Mặc định top 5."""
        limit, error = _limit(5, maximum=200)
        if error:
            return jsonify({"error": error}), 400
        state, error = _state()
        if error:
            return jsonify({"error": error}), 400
        try:
            data = gateway.fetch_all(
                f"""
                WITH {_VALID_SALES},
                by_state_cat AS (
                    SELECT
                        customer_state,
                        category,
                        round(sum(price), 2) AS revenue,
                        count(*) AS items_sold,
                        count(DISTINCT order_id) AS orders
                    FROM valid_sales
                    WHERE customer_state IS NOT NULL
                      AND (%s = '' OR customer_state = %s)
                    GROUP BY customer_state, category
                ),
                ranked AS (
                    SELECT
                        *,
                        row_number() OVER (
                            PARTITION BY customer_state
                            ORDER BY revenue DESC, items_sold DESC, category
                        ) AS rn
                    FROM by_state_cat
                )
                SELECT
                    customer_state,
                    category,
                    revenue,
                    items_sold,
                    orders,
                    rn AS rank_in_state
                FROM ranked
                WHERE rn <= %s
                ORDER BY customer_state, rn
                """,
                _period_params(state, state, limit),
            )
            return _ok(
                "rank",
                data,
                state=state or None,
                **_period_fields(),
                note="rank_in_state là hạng trong bang. Không cộng orders của các danh mục trong cùng bang.",
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    @bp.route("/api/product-geo", methods=["GET"])
    def product_geo_main():
        """Điều hướng theo operation, cùng vai trò với /api/olap của màn thời gian."""
        operation = request.args.get("operation", "summary")
        handlers = {
            "summary": product_summary,
            "categories": product_categories,
            "sellers": product_sellers,
            "pareto": product_pareto,
            "freight": product_freight,
            "states": product_states,
            "rollup": product_rollup,
            "drilldown": product_drilldown,
            "slice": product_slice,
            "dice": product_dice,
            "rank": product_rank,
            "periods": product_periods,
        }
        handler = handlers.get(operation)
        if handler is None:
            return jsonify({"error": "operation không hợp lệ"}), 400
        return handler()


    for _suffix, _view in (
        ("/summary", product_summary),
        ("/categories", product_categories),
        ("/sellers", product_sellers),
        ("/pareto", product_pareto),
        ("/freight", product_freight),
        ("/states", product_states),
        ("/rollup", product_rollup),
        ("/drilldown", product_drilldown),
        ("/slice", product_slice),
        ("/dice", product_dice),
        ("/periods", product_periods),
        ("/rank", product_rank),
        ("", product_geo_main),
    ):
        bp.add_url_rule(
            f"/api/olap/product{_suffix}",
            endpoint=f"/api/olap/product{_suffix}",
            view_func=_view,
            methods=["GET"],
        )
    return bp

