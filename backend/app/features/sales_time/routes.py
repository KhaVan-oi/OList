"""Màn Thời gian. Route chỉ validate + gọi QueryGateway; SQL chạy qua gateway."""

from flask import Blueprint, jsonify, request

from app.common.query_gateway import QueryGateway
from app.features.sales_time import growth


def _validate_time_level(level: str) -> bool:
    return level in ('month', 'quarter', 'year')


def _validate_year(year) -> bool:
    try:
        y = int(year)
        return 2016 <= y <= 2018
    except (TypeError, ValueError):
        return False


def _validate_quarter(q) -> bool:
    try:
        return int(q) in (1, 2, 3, 4)
    except (TypeError, ValueError):
        return False


def _validate_month(m) -> bool:
    try:
        return 1 <= int(m) <= 12
    except (TypeError, ValueError):
        return False


def create_sales_time_blueprint(gateway: QueryGateway):
    bp = Blueprint("sales_time", __name__)

    # ---------------------------------------------------------------------------
    # Endpoint 1-3: /api/olap/monthly | quarterly | yearly
    # SQL dựng ở growth.py. Năm và quý tính tăng trưởng CÙNG KỲ (xem docstring growth.py).
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/monthly', methods=['GET'])
    def olap_monthly():
        """KPI theo tháng kèm MoM và YTD. Tháng không có giao dịch giữ NULL. Tham số tùy chọn: year."""
        year = request.args.get('year')
        if year and not _validate_year(year):
            return jsonify({'error': 'Tham số year không hợp lệ (2016-2018)'}), 400
        try:
            data = gateway.fetch_all(*growth.month_sql(int(year) if year else None))
            return jsonify({'status': 'ok', 'level': 'month', 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @bp.route('/api/olap/quarterly', methods=['GET'])
    def olap_quarterly():
        """KPI theo quý kèm QoQ cùng kỳ. Tham số tùy chọn: year."""
        year = request.args.get('year')
        if year and not _validate_year(year):
            return jsonify({'error': 'Tham số year không hợp lệ (2016-2018)'}), 400
        try:
            data = gateway.fetch_all(*growth.quarter_sql(int(year) if year else None))
            return jsonify({'status': 'ok', 'level': 'quarter', 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @bp.route('/api/olap/yearly', methods=['GET'])
    def olap_yearly():
        """KPI theo năm kèm YoY cùng kỳ."""
        try:
            data = gateway.fetch_all(*growth.year_sql())
            return jsonify({'status': 'ok', 'level': 'year', 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 4: /api/olap/rollup — Roll-up Tháng → Quý → Năm → Grand Total
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/rollup', methods=['GET'])
    def olap_rollup():
        """
        Roll-up: GROUP BY ROLLUP(year, quarter, month).
        grouping_level: 0=chi tiết tháng, 1=subtotal quý, 3=subtotal năm, 7=grand total
        """
        sql = """
        SELECT
            CASE WHEN GROUPING(d.year)    = 1 THEN NULL ELSE d.year    END AS year,
            CASE WHEN GROUPING(d.quarter) = 1 THEN NULL ELSE d.quarter END AS quarter,
            CASE WHEN GROUPING(d.month)   = 1 THEN NULL ELSE d.month   END AS month,
            GROUPING(d.year, d.quarter, d.month) AS grouping_level,
            ROUND(SUM(fs.price),         2) AS product_sales,
            ROUND(SUM(fs.freight_value), 2) AS freight_value,
            COUNT(*)                        AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        WHERE fco.order_status = 'delivered'
        GROUP BY ROLLUP(d.year, d.quarter, d.month)
        ORDER BY
            d.year    NULLS LAST,
            d.quarter NULLS LAST,
            d.month   NULLS LAST
        """
        try:
            data = gateway.fetch_all(sql)
            return jsonify({'status': 'ok', 'operation': 'rollup', 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 5: /api/olap/timeanalysis — Phân tích thời gian thống nhất
    # Hợp nhất Roll-up và Drill-down theo cấp người dùng chọn
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/timeanalysis', methods=['GET'])
    def olap_timeanalysis():
        """
        Phân tích thời gian thống nhất (thay Roll-up + Drill-down).
        Params:
          - level: day | month | quarter | year  (bắt buộc)
          - year: lọc theo năm (tùy chọn)
          - quarter: lọc theo quý (tùy chọn, chỉ hiệu quả khi level=day hoặc month)
          - month: lọc theo tháng (tùy chọn, chỉ hiệu quả khi level=day)
          - weekend: 1 (cuối tuần) / 0 (ngày thường) — chỉ áp dụng khi level=day
        """
        level   = request.args.get('level', 'month')  # day|month|quarter|year
        year    = request.args.get('year')
        quarter = request.args.get('quarter')
        month   = request.args.get('month')
        weekend = request.args.get('weekend')  # '1'=cuối tuần, '0'=ngày thường

        if level not in ('day', 'month', 'quarter', 'year'):
            return jsonify({'error': 'level phải là day, month, quarter hoặc year'}), 400
        if year    and not _validate_year(year):
            return jsonify({'error': 'Tham số year không hợp lệ (2016-2018)'}), 400
        if quarter and not _validate_quarter(quarter):
            return jsonify({'error': 'Tham số quarter không hợp lệ (1-4)'}), 400
        if month   and not _validate_month(month):
            return jsonify({'error': 'Tham số month không hợp lệ (1-12)'}), 400

        conditions = ["fco.order_status = 'delivered'"]
        if year:    conditions.append(f"d.year = {int(year)}")
        if quarter: conditions.append(f"d.quarter = {int(quarter)}")
        if month:   conditions.append(f"d.month = {int(month)}")
        # weekend filter chỉ áp dụng cho level=day để lọc hàng, không group
        if level == 'day':
            if weekend == '1': conditions.append("d.is_weekend = TRUE")
            if weekend == '0': conditions.append("d.is_weekend = FALSE")

        where = "WHERE " + " AND ".join(conditions)

        if level == 'day':
            # Grain: mỗi ngày — trả full_date, is_weekend, day_of_month
            sql = f"""
            SELECT
                d.year,
                d.month,
                d.day_of_month,
                d.full_date,
                d.is_weekend,
                ROUND(SUM(fs.price),         2) AS product_sales,
                ROUND(SUM(fs.freight_value), 2) AS freight_value,
                COUNT(*)                        AS order_item_count
            FROM dw.fact_sales fs
            JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
            JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
            {where}
            GROUP BY d.year, d.month, d.day_of_month, d.full_date, d.is_weekend
            ORDER BY d.full_date
            """
            params = ()

        elif level == 'month':
            # Chuỗi tháng liên tục; MoM tính trên toàn chuỗi rồi mới lọc năm/quý
            sql, params = growth.month_sql(int(year) if year else None, int(quarter) if quarter else None)

        elif level == 'quarter':
            # QoQ cùng kỳ, tính trên toàn chuỗi rồi mới lọc năm (quý 1 vẫn so được với quý 4 năm trước)
            sql, params = growth.quarter_sql(int(year) if year else None)

        else:  # level == 'year'
            sql, params = growth.year_sql()

        try:
            data = gateway.fetch_all(sql, params)
            # Chuyển đổi full_date sang string nếu có
            for row in data:
                if 'full_date' in row and row['full_date'] is not None:
                    row['full_date'] = str(row['full_date'])
                if 'is_weekend' in row and row['is_weekend'] is not None:
                    row['is_weekend'] = bool(row['is_weekend'])
            return jsonify({
                'status': 'ok',
                'operation': 'timeanalysis',
                'level': level,
                'filters': {
                    'year': int(year) if year else None,
                    'quarter': int(quarter) if quarter else None,
                    'month': int(month) if month else None,
                    'weekend': weekend
                },
                'data': data
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 6 (legacy): /api/olap/drilldown — Drill-down theo chiều thời gian
    # Giữ lại để tương thích, nhưng logic chính đã chuyển sang /timeanalysis
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/drilldown', methods=['GET'])
    def olap_drilldown():
        """
        Drill-down legacy endpoint. Chuyển hướng sang timeanalysis với logic tương đương.
          GET /api/olap/drilldown                      → tổng theo năm
          GET /api/olap/drilldown?year=2017            → theo quý trong năm
          GET /api/olap/drilldown?year=2017&quarter=3  → theo tháng
          GET /api/olap/drilldown?year=2017&month=9    → theo ngày (từng ngày)
          GET /api/olap/drilldown?year=2017&month=9&weekend=1 → ngày cuối tuần trong tháng (từng ngày)
        """
        year    = request.args.get('year')
        quarter = request.args.get('quarter')
        month   = request.args.get('month')
        weekend = request.args.get('weekend')

        if year    and not _validate_year(year):
            return jsonify({'error': 'Tham số year không hợp lệ'}), 400
        if quarter and not _validate_quarter(quarter):
            return jsonify({'error': 'Tham số quarter không hợp lệ (1-4)'}), 400
        if month   and not _validate_month(month):
            return jsonify({'error': 'Tham số month không hợp lệ (1-12)'}), 400

        conditions = ["fco.order_status = 'delivered'"]
        if year:    conditions.append(f"d.year = {int(year)}")
        if quarter: conditions.append(f"d.quarter = {int(quarter)}")
        if month:   conditions.append(f"d.month = {int(month)}")
        if weekend == '1': conditions.append("d.is_weekend = TRUE")
        if weekend == '0': conditions.append("d.is_weekend = FALSE")
        where = "WHERE " + " AND ".join(conditions)

        # Xác định cấp nhóm và cột hiển thị
        if not year:
            group_by = "d.year"
            select_cols = "d.year, NULL::int AS quarter, NULL::int AS month, NULL::date AS full_date, NULL::boolean AS is_weekend"
            order_by = "d.year"
        elif not month and not quarter:
            group_by = "d.year, d.quarter"
            select_cols = "d.year, d.quarter, NULL::int AS month, NULL::date AS full_date, NULL::boolean AS is_weekend"
            order_by = "d.year, d.quarter"
        elif quarter and not month:
            group_by = "d.year, d.quarter, d.month"
            select_cols = "d.year, d.quarter, d.month, NULL::date AS full_date, NULL::boolean AS is_weekend"
            order_by = "d.year, d.quarter, d.month"
        else:
            # month được chỉ định → hiển thị từng ngày (kể cả khi có weekend filter)
            group_by = "d.year, d.month, d.day_of_month, d.full_date, d.is_weekend"
            select_cols = "d.year, NULL::int AS quarter, d.month, d.full_date, d.is_weekend"
            order_by = "d.full_date"

        sql = f"""
        SELECT
            {select_cols},
            ROUND(SUM(fs.price),         2) AS product_sales,
            ROUND(SUM(fs.freight_value), 2) AS freight_value,
            COUNT(*)                        AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        {where}
        GROUP BY {group_by}
        ORDER BY {order_by}
        """

        try:
            data = gateway.fetch_all(sql)
            for row in data:
                if 'full_date' in row and row['full_date'] is not None:
                    row['full_date'] = str(row['full_date'])
                if 'is_weekend' in row and row['is_weekend'] is not None:
                    row['is_weekend'] = bool(row['is_weekend'])
            return jsonify({'status': 'ok', 'operation': 'drilldown', 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 7: /api/olap/slice — Cố định 1 chiều, xem tập con
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/slice', methods=['GET'])
    def olap_slice():
        """
        Slice: cố định year, trả về KPI theo tháng kèm MoM.
        Tháng 1 vẫn có MoM từ tháng 12 năm trước.
        Tháng thiếu dữ liệu: giữ NULL (không gán 0).
        Params:
          - year (bắt buộc): 2016-2018
        """
        year = request.args.get('year')
        if not year or not _validate_year(year):
            return jsonify({'error': 'Tham số year bắt buộc và phải thuộc 2016-2018'}), 400

        y = int(year)
        prev_year = y - 1

        sql = f"""
        WITH
        monthly_raw AS (
            SELECT d.year, d.month,
                SUM(fs.price)         AS product_sales,
                SUM(fs.freight_value) AS freight_value,
                COUNT(*)              AS order_item_count
            FROM dw.fact_sales fs
            JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
            JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
            WHERE fco.order_status = 'delivered'
              AND (d.year = {y} OR (d.year = {prev_year} AND d.month = 12))
            GROUP BY d.year, d.month
        ),
        month_series AS (
            SELECT s_year AS year, s_month AS month
            FROM (
                SELECT {prev_year} AS s_year, 12 AS s_month
                UNION ALL
                SELECT {y}, generate_series(1, 12)
            ) t
        ),
        slice_base AS (
            SELECT
                ms.year, ms.month,
                mr.product_sales,       -- NULL nếu tháng không có giao dịch
                mr.freight_value,
                mr.order_item_count
            FROM month_series ms
            LEFT JOIN monthly_raw mr USING (year, month)
        ),
        slice_metrics AS (
            SELECT
                year, month, product_sales, freight_value, order_item_count,
                CASE
                    WHEN product_sales IS NULL OR LAG(product_sales) OVER (ORDER BY year, month) IS NULL
                         OR LAG(product_sales) OVER (ORDER BY year, month) = 0
                    THEN NULL
                    ELSE ROUND(
                        (product_sales - LAG(product_sales) OVER (ORDER BY year, month))
                        / LAG(product_sales) OVER (ORDER BY year, month) * 100, 2)
                END AS mom_product_sales_pct,
                CASE
                    WHEN freight_value IS NULL OR LAG(freight_value) OVER (ORDER BY year, month) IS NULL
                         OR LAG(freight_value) OVER (ORDER BY year, month) = 0
                    THEN NULL
                    ELSE ROUND(
                        (freight_value - LAG(freight_value) OVER (ORDER BY year, month))
                        / LAG(freight_value) OVER (ORDER BY year, month) * 100, 2)
                END AS mom_freight_value_pct,
                CASE
                    WHEN order_item_count IS NULL OR LAG(order_item_count) OVER (ORDER BY year, month) IS NULL
                         OR LAG(order_item_count) OVER (ORDER BY year, month) = 0
                    THEN NULL
                    ELSE ROUND(
                        (order_item_count - LAG(order_item_count) OVER (ORDER BY year, month))::numeric
                        / LAG(order_item_count) OVER (ORDER BY year, month) * 100, 2)
                END AS mom_order_item_count_pct,
                -- YTD: SUM bỏ qua NULL (built-in), NULL nếu không có gì cả
                SUM(product_sales)    OVER (PARTITION BY year ORDER BY month) AS ytd_product_sales,
                SUM(freight_value)    OVER (PARTITION BY year ORDER BY month) AS ytd_freight_value,
                SUM(order_item_count) OVER (PARTITION BY year ORDER BY month) AS ytd_order_item_count
            FROM slice_base
        )
        SELECT
            year, month,
            ROUND(product_sales,    2) AS product_sales,
            ROUND(freight_value,    2) AS freight_value,
            order_item_count,
            mom_product_sales_pct,
            mom_freight_value_pct,
            mom_order_item_count_pct,
            ROUND(ytd_product_sales,    2) AS ytd_product_sales,
            ROUND(ytd_freight_value,    2) AS ytd_freight_value,
            ytd_order_item_count
        FROM slice_metrics
        WHERE year = {y}
        ORDER BY month
        """

        try:
            data = gateway.fetch_all(sql)
            return jsonify({'status': 'ok', 'operation': 'slice',
                            'filters': {'year': y}, 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 8: /api/olap/dice — Chọn tập con đa điều kiện
    # Khi có weekend filter: trả từng ngày (full_date) kèm is_weekend
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/dice', methods=['GET'])
    def olap_dice():
        """
        Dice: lọc nhiều chiều đồng thời.
        Params (tất cả tùy chọn):
          - year_from, year_to: phạm vi năm
          - quarter: 1-4
          - month: 1-12
          - weekend: 1 (cuối tuần) / 0 (ngày thường)
          - group_by: year | quarter | month | day (mặc định: year)
            Khi weekend được chỉ định, group_by tự động chuyển sang 'day' để không gộp ngày.
        """
        year_from = request.args.get('year_from', '2016')
        year_to   = request.args.get('year_to',   '2018')
        quarter   = request.args.get('quarter')
        month     = request.args.get('month')
        weekend   = request.args.get('weekend')
        group_by_param = request.args.get('group_by', 'year')

        # Validate
        if not _validate_year(year_from) or not _validate_year(year_to):
            return jsonify({'error': 'year_from / year_to không hợp lệ (2016-2018)'}), 400
        if quarter and not _validate_quarter(quarter):
            return jsonify({'error': 'quarter không hợp lệ (1-4)'}), 400
        if month and not _validate_month(month):
            return jsonify({'error': 'month không hợp lệ (1-12)'}), 400
        if group_by_param not in ('year', 'quarter', 'month', 'day'):
            return jsonify({'error': 'group_by phải là year, quarter, month hoặc day'}), 400

        conditions = [
            "fco.order_status = 'delivered'",
            f"d.year BETWEEN {int(year_from)} AND {int(year_to)}"
        ]
        if quarter: conditions.append(f"d.quarter = {int(quarter)}")
        if month:   conditions.append(f"d.month   = {int(month)}")
        if weekend == '1': conditions.append("d.is_weekend = TRUE")
        if weekend == '0': conditions.append("d.is_weekend = FALSE")

        where = "WHERE " + " AND ".join(conditions)

        # Nếu có weekend filter → buộc group theo ngày để không gộp dữ liệu
        effective_group = group_by_param
        if weekend is not None and weekend != '':
            effective_group = 'day'

        if effective_group == 'year':
            select_time  = "d.year, NULL::int AS quarter, NULL::int AS month, NULL::date AS full_date, NULL::boolean AS is_weekend"
            group_clause = "d.year"
            order_clause = "d.year"
        elif effective_group == 'quarter':
            select_time  = "d.year, d.quarter, NULL::int AS month, NULL::date AS full_date, NULL::boolean AS is_weekend"
            group_clause = "d.year, d.quarter"
            order_clause = "d.year, d.quarter"
        elif effective_group == 'month':
            select_time  = "d.year, d.quarter, d.month, NULL::date AS full_date, NULL::boolean AS is_weekend"
            group_clause = "d.year, d.quarter, d.month"
            order_clause = "d.year, d.month"
        else:  # day
            select_time  = "d.year, d.quarter, d.month, d.full_date, d.is_weekend"
            group_clause = "d.year, d.quarter, d.month, d.full_date, d.is_weekend"
            order_clause = "d.full_date"

        sql = f"""
        SELECT
            {select_time},
            ROUND(SUM(fs.price),         2) AS product_sales,
            ROUND(SUM(fs.freight_value), 2) AS freight_value,
            COUNT(*)                        AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        {where}
        GROUP BY {group_clause}
        ORDER BY {order_clause}
        """

        try:
            data = gateway.fetch_all(sql)
            for row in data:
                if 'full_date' in row and row['full_date'] is not None:
                    row['full_date'] = str(row['full_date'])
                if 'is_weekend' in row and row['is_weekend'] is not None:
                    row['is_weekend'] = bool(row['is_weekend'])
            filters = {
                'year_from': int(year_from), 'year_to': int(year_to),
                'quarter': int(quarter) if quarter else None,
                'month': int(month) if month else None,
                'weekend': weekend,
                'group_by': effective_group
            }
            return jsonify({'status': 'ok', 'operation': 'dice',
                            'filters': filters, 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 9: /api/olap/pivot — Ma trận Tháng x Năm
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap/pivot', methods=['GET'])
    def olap_pivot():
        """
        Pivot: ma trận tháng x năm.
        Params:
          - kpi: sales (default) | freight | count
          - type: value (default) | growth (MoM %)
        NULL cho ô không có dữ liệu (không gán 0).
        """
        kpi   = request.args.get('kpi',  'sales')
        ptype = request.args.get('type', 'value')

        if kpi not in ('sales', 'freight', 'count'):
            return jsonify({'error': 'kpi phải là sales, freight hoặc count'}), 400
        if ptype not in ('value', 'growth'):
            return jsonify({'error': 'type phải là value hoặc growth'}), 400

        kpi_expr = {
            'sales':   'SUM(fs.price)',
            'freight': 'SUM(fs.freight_value)',
            'count':   'COUNT(*)'
        }[kpi]

        if ptype == 'value':
            # NULL nếu không có dữ liệu cho năm đó trong tháng đó
            sql = f"""
            WITH
            month_series AS (
                SELECT generate_series(1, 12) AS month
            ),
            raw_data AS (
                SELECT d.year, d.month, ROUND({kpi_expr}::numeric, 2) AS kpi_val
                FROM dw.fact_sales fs
                JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
                JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
                WHERE fco.order_status = 'delivered'
                  AND d.year IN (2016, 2017, 2018)
                GROUP BY d.year, d.month
            )
            SELECT
                ms.month,
                MAX(rd.kpi_val) FILTER (WHERE rd.year = 2016) AS val_2016,
                MAX(rd.kpi_val) FILTER (WHERE rd.year = 2017) AS val_2017,
                MAX(rd.kpi_val) FILTER (WHERE rd.year = 2018) AS val_2018
            FROM month_series ms
            LEFT JOIN raw_data rd ON rd.month = ms.month
            GROUP BY ms.month
            ORDER BY ms.month
            """
        else:
            # MoM growth: NULL cho tháng đầu tiên hoặc khi tháng trước thiếu dữ liệu/= 0
            sql = f"""
            WITH
            monthly_all AS (
                SELECT d.year, d.month, {kpi_expr} AS kpi_val
                FROM dw.fact_sales fs
                JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
                JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
                WHERE fco.order_status = 'delivered'
                GROUP BY d.year, d.month
            ),
            mys AS (
                SELECT y, m
                FROM generate_series(2016, 2018) AS y,
                     generate_series(1, 12)      AS m
            ),
            full_base AS (
                SELECT mys.y AS year, mys.m AS month,
                    ma.kpi_val   -- NULL nếu không có dữ liệu
                FROM mys
                LEFT JOIN monthly_all ma ON ma.year = mys.y AND ma.month = mys.m
            ),
            mom_calc AS (
                SELECT year, month,
                    CASE
                        WHEN kpi_val IS NULL OR LAG(kpi_val) OVER (PARTITION BY year ORDER BY month) IS NULL
                             OR LAG(kpi_val) OVER (PARTITION BY year ORDER BY month) = 0
                        THEN NULL
                        ELSE ROUND(
                            (kpi_val - LAG(kpi_val) OVER (PARTITION BY year ORDER BY month))
                            / LAG(kpi_val) OVER (PARTITION BY year ORDER BY month) * 100, 2)
                    END AS mom_pct
                FROM full_base
            )
            SELECT
                month,
                MAX(CASE WHEN year = 2016 THEN mom_pct END) AS val_2016,
                MAX(CASE WHEN year = 2017 THEN mom_pct END) AS val_2017,
                MAX(CASE WHEN year = 2018 THEN mom_pct END) AS val_2018
            FROM mom_calc
            GROUP BY month
            ORDER BY month
            """

        try:
            data = gateway.fetch_all(sql)
            return jsonify({'status': 'ok', 'operation': 'pivot',
                            'kpi': kpi, 'type': ptype, 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint 10: /api/sales-time/matrix — Ma trận Tháng (hàng) × Năm (cột)
    # Trả dạng dài (year, month, 3 measure); frontend chọn measure đang xem.
    # Dùng chung bộ lọc với timeanalysis / dice nên đổi chế độ bảng không mất lọc.
    # ---------------------------------------------------------------------------
    @bp.route('/api/sales-time/matrix', methods=['GET'])
    def olap_matrix():
        """
        Params (tùy chọn): year_from, year_to (mặc định 2016-2018), quarter, month,
        weekend (1 = cuối tuần, 0 = ngày thường).
        Ô không có giao dịch không xuất hiện trong kết quả (frontend hiển thị trống, không gán 0).
        """
        year_from = request.args.get('year_from', '2016')
        year_to   = request.args.get('year_to',   '2018')
        quarter   = request.args.get('quarter')
        month     = request.args.get('month')
        weekend   = request.args.get('weekend')

        if not _validate_year(year_from) or not _validate_year(year_to):
            return jsonify({'error': 'year_from / year_to không hợp lệ (2016-2018)'}), 400
        if int(year_from) > int(year_to):
            return jsonify({'error': 'year_from không được lớn hơn year_to'}), 400
        if quarter and not _validate_quarter(quarter):
            return jsonify({'error': 'quarter không hợp lệ (1-4)'}), 400
        if month and not _validate_month(month):
            return jsonify({'error': 'month không hợp lệ (1-12)'}), 400

        conditions = [
            "fco.order_status = 'delivered'",
            f"d.year BETWEEN {int(year_from)} AND {int(year_to)}",
        ]
        if quarter: conditions.append(f"d.quarter = {int(quarter)}")
        if month:   conditions.append(f"d.month = {int(month)}")
        if weekend == '1': conditions.append("d.is_weekend = TRUE")
        if weekend == '0': conditions.append("d.is_weekend = FALSE")

        sql = f"""
        SELECT
            d.year, d.month,
            ROUND(SUM(fs.price),         2) AS product_sales,
            ROUND(SUM(fs.freight_value), 2) AS freight_value,
            COUNT(*)                        AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        WHERE {" AND ".join(conditions)}
        GROUP BY d.year, d.month
        ORDER BY d.month, d.year
        """
        try:
            data = gateway.fetch_all(sql)
            return jsonify({'status': 'ok', 'operation': 'matrix',
                            'year_from': int(year_from), 'year_to': int(year_to), 'data': data})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    # ---------------------------------------------------------------------------
    # Endpoint tổng hợp: /api/olap — Routing theo time_level và operation
    # ---------------------------------------------------------------------------
    @bp.route('/api/olap', methods=['GET'])
    def olap_main():
        """
        Endpoint tổng hợp, điều hướng theo tham số:
          - time_level: month | quarter | year
          - operation: rollup | drilldown | timeanalysis | slice | dice | pivot | summary
        Nếu không có operation, mặc định trả summary theo time_level.
        """
        level     = request.args.get('time_level', 'month')
        operation = request.args.get('operation',  'summary')

        if not _validate_time_level(level):
            return jsonify({'error': 'time_level phải là month, quarter hoặc year'}), 400

        # Điều hướng sang endpoint chuyên biệt
        if operation == 'rollup':
            return olap_rollup()
        elif operation == 'timeanalysis':
            return olap_timeanalysis()
        elif operation == 'drilldown':
            return olap_drilldown()
        elif operation == 'slice':
            return olap_slice()
        elif operation == 'dice':
            return olap_dice()
        elif operation == 'pivot':
            return olap_pivot()
        else:
            # summary: tuỳ theo time_level
            if level == 'month':
                return olap_monthly()
            elif level == 'quarter':
                return olap_quarterly()
            else:
                return olap_yearly()


    # Tên mới theo từng màn. URL /api/olap/* giữ nguyên cho client cũ.
    for _path, _view in (
        ('/api/sales-time/monthly', olap_monthly),
        ('/api/sales-time/quarterly', olap_quarterly),
        ('/api/sales-time/yearly', olap_yearly),
        ('/api/sales-time/rollup', olap_rollup),
        ('/api/sales-time/timeanalysis', olap_timeanalysis),
        ('/api/sales-time/drilldown', olap_drilldown),
        ('/api/sales-time/slice', olap_slice),
        ('/api/sales-time/dice', olap_dice),
        ('/api/sales-time/pivot', olap_pivot),
        ('/api/sales-time', olap_main),
    ):
        bp.add_url_rule(_path, endpoint=_path, view_func=_view, methods=['GET'])
    return bp

