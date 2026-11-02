"""
backend/app.py
Flask API — OLAP Sales & Time cho Olist Data Warehouse
Tái sử dụng db_connect.py từ thư mục cha.
"""

import sys
import os

# Thêm thư mục cha vào path để import db_connect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, jsonify, request
from flask_cors import CORS
from db_connect import get_connection

app = Flask(__name__)
CORS(app)  # Cho phép frontend truy cập API


# ---------------------------------------------------------------------------
# Hàm tiện ích
# ---------------------------------------------------------------------------

def _rows_to_dicts(cur):
    """Chuyển kết quả cursor sang list of dict."""
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


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


# ---------------------------------------------------------------------------
# Endpoint 1: /api/olap/monthly — KPI tháng + MoM Growth + YTD
# Dùng NULL (không dùng COALESCE=0) cho tháng không có giao dịch trong phạm vi
# ---------------------------------------------------------------------------
@app.route('/api/olap/monthly', methods=['GET'])
def olap_monthly():
    """
    Trả về KPI tổng hợp theo tháng kèm MoM Growth và YTD.
    Tháng thiếu dữ liệu: giữ NULL (không gán 0).
    Query params tùy chọn:
      - year: lọc theo năm (2016-2018)
    """
    year_filter = request.args.get('year')
    if year_filter and not _validate_year(year_filter):
        return jsonify({'error': 'Tham số year không hợp lệ (2016-2018)'}), 400

    sql = """
    WITH
    monthly_raw AS (
        SELECT
            d.year, d.month,
            SUM(fs.price)         AS product_sales,
            SUM(fs.freight_value) AS freight_value,
            COUNT(*)              AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        WHERE fco.order_status = 'delivered'
        GROUP BY d.year, d.month
    ),
    month_series AS (
        SELECT
            EXTRACT(YEAR  FROM gs)::int AS year,
            EXTRACT(MONTH FROM gs)::int AS month
        FROM generate_series(
            (SELECT DATE_TRUNC('month', MIN(full_date)) FROM dw.dim_date
             WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
            (SELECT DATE_TRUNC('month', MAX(full_date)) FROM dw.dim_date
             WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
            INTERVAL '1 month'
        ) AS gs
    ),
    monthly_base AS (
        SELECT
            ms.year, ms.month,
            mr.product_sales,       -- NULL nếu tháng không có giao dịch
            mr.freight_value,
            mr.order_item_count
        FROM month_series ms
        LEFT JOIN monthly_raw mr ON mr.year = ms.year AND mr.month = ms.month
    ),
    monthly_with_metrics AS (
        SELECT
            year, month, product_sales, freight_value, order_item_count,
            -- MoM Growth: NULL nếu tháng hiện tại hoặc tháng trước thiếu dữ liệu, hoặc tháng trước = 0
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
            -- YTD: lũy kế, NULL nếu không có dữ liệu
            SUM(product_sales)    OVER (PARTITION BY year ORDER BY month) AS ytd_product_sales,
            SUM(freight_value)    OVER (PARTITION BY year ORDER BY month) AS ytd_freight_value,
            SUM(order_item_count) OVER (PARTITION BY year ORDER BY month) AS ytd_order_item_count
        FROM monthly_base
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
    FROM monthly_with_metrics
    {where}
    ORDER BY year, month
    """

    where_clause = f"WHERE year = {int(year_filter)}" if year_filter else ""
    sql = sql.format(where=where_clause)

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
        return jsonify({'status': 'ok', 'level': 'month', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint 2: /api/olap/quarterly — KPI quý + QoQ Growth + YTD
# ---------------------------------------------------------------------------
@app.route('/api/olap/quarterly', methods=['GET'])
def olap_quarterly():
    """
    Trả về KPI tổng hợp theo quý kèm QoQ Growth và YTD.
    Quý thiếu dữ liệu: giữ NULL.
    Query params tùy chọn:
      - year: lọc theo năm
    """
    year_filter = request.args.get('year')
    if year_filter and not _validate_year(year_filter):
        return jsonify({'error': 'Tham số year không hợp lệ (2016-2018)'}), 400

    sql = """
    WITH
    quarterly_raw AS (
        SELECT
            d.year, d.quarter,
            SUM(fs.price)         AS product_sales,
            SUM(fs.freight_value) AS freight_value,
            COUNT(*)              AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        WHERE fco.order_status = 'delivered'
        GROUP BY d.year, d.quarter
    ),
    quarter_series AS (
        SELECT
            EXTRACT(YEAR    FROM gs)::int AS year,
            EXTRACT(QUARTER FROM gs)::int AS quarter
        FROM generate_series(
            (SELECT DATE_TRUNC('quarter', MIN(full_date)) FROM dw.dim_date
             WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
            (SELECT DATE_TRUNC('quarter', MAX(full_date)) FROM dw.dim_date
             WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
            INTERVAL '3 months'
        ) AS gs
    ),
    quarterly_base AS (
        SELECT
            qs.year, qs.quarter,
            qr.product_sales,
            qr.freight_value,
            qr.order_item_count
        FROM quarter_series qs
        LEFT JOIN quarterly_raw qr ON qr.year = qs.year AND qr.quarter = qs.quarter
    ),
    quarterly_with_metrics AS (
        SELECT
            year, quarter, product_sales, freight_value, order_item_count,
            CASE
                WHEN product_sales IS NULL OR LAG(product_sales) OVER (ORDER BY year, quarter) IS NULL
                     OR LAG(product_sales) OVER (ORDER BY year, quarter) = 0
                THEN NULL
                ELSE ROUND(
                    (product_sales - LAG(product_sales) OVER (ORDER BY year, quarter))
                    / LAG(product_sales) OVER (ORDER BY year, quarter) * 100, 2)
            END AS qoq_product_sales_pct,
            CASE
                WHEN freight_value IS NULL OR LAG(freight_value) OVER (ORDER BY year, quarter) IS NULL
                     OR LAG(freight_value) OVER (ORDER BY year, quarter) = 0
                THEN NULL
                ELSE ROUND(
                    (freight_value - LAG(freight_value) OVER (ORDER BY year, quarter))
                    / LAG(freight_value) OVER (ORDER BY year, quarter) * 100, 2)
            END AS qoq_freight_value_pct,
            CASE
                WHEN order_item_count IS NULL OR LAG(order_item_count) OVER (ORDER BY year, quarter) IS NULL
                     OR LAG(order_item_count) OVER (ORDER BY year, quarter) = 0
                THEN NULL
                ELSE ROUND(
                    (order_item_count - LAG(order_item_count) OVER (ORDER BY year, quarter))::numeric
                    / LAG(order_item_count) OVER (ORDER BY year, quarter) * 100, 2)
            END AS qoq_order_item_count_pct,
            SUM(product_sales)    OVER (PARTITION BY year ORDER BY quarter) AS ytd_product_sales,
            SUM(freight_value)    OVER (PARTITION BY year ORDER BY quarter) AS ytd_freight_value,
            SUM(order_item_count) OVER (PARTITION BY year ORDER BY quarter) AS ytd_order_item_count
        FROM quarterly_base
    )
    SELECT
        year, quarter,
        ROUND(product_sales,    2) AS product_sales,
        ROUND(freight_value,    2) AS freight_value,
        order_item_count,
        qoq_product_sales_pct,
        qoq_freight_value_pct,
        qoq_order_item_count_pct,
        ROUND(ytd_product_sales,    2) AS ytd_product_sales,
        ROUND(ytd_freight_value,    2) AS ytd_freight_value,
        ytd_order_item_count
    FROM quarterly_with_metrics
    {where}
    ORDER BY year, quarter
    """

    where_clause = f"WHERE year = {int(year_filter)}" if year_filter else ""
    sql = sql.format(where=where_clause)

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
        return jsonify({'status': 'ok', 'level': 'quarter', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint 3: /api/olap/yearly — KPI năm + YoY Growth
# ---------------------------------------------------------------------------
@app.route('/api/olap/yearly', methods=['GET'])
def olap_yearly():
    """Trả về KPI tổng hợp theo năm kèm YoY Growth. Năm thiếu giữ NULL."""
    sql = """
    WITH
    yearly_raw AS (
        SELECT
            d.year,
            SUM(fs.price)         AS product_sales,
            SUM(fs.freight_value) AS freight_value,
            COUNT(*)              AS order_item_count
        FROM dw.fact_sales fs
        JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
        JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
        WHERE fco.order_status = 'delivered'
        GROUP BY d.year
    ),
    year_series AS (
        SELECT generate_series(
            (SELECT MIN(year) FROM dw.dim_date
             WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
            (SELECT MAX(year) FROM dw.dim_date
             WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales))
        )::int AS year
    ),
    yearly_base AS (
        SELECT
            ys.year,
            yr.product_sales,
            yr.freight_value,
            yr.order_item_count
        FROM year_series ys
        LEFT JOIN yearly_raw yr USING (year)
    )
    SELECT
        year,
        ROUND(product_sales,    2) AS product_sales,
        ROUND(freight_value,    2) AS freight_value,
        order_item_count,
        CASE
            WHEN product_sales IS NULL OR LAG(product_sales) OVER (ORDER BY year) IS NULL
                 OR LAG(product_sales) OVER (ORDER BY year) = 0
            THEN NULL
            ELSE ROUND(
                (product_sales - LAG(product_sales) OVER (ORDER BY year))
                / LAG(product_sales) OVER (ORDER BY year) * 100, 2)
        END AS yoy_product_sales_pct,
        CASE
            WHEN freight_value IS NULL OR LAG(freight_value) OVER (ORDER BY year) IS NULL
                 OR LAG(freight_value) OVER (ORDER BY year) = 0
            THEN NULL
            ELSE ROUND(
                (freight_value - LAG(freight_value) OVER (ORDER BY year))
                / LAG(freight_value) OVER (ORDER BY year) * 100, 2)
        END AS yoy_freight_value_pct,
        CASE
            WHEN order_item_count IS NULL OR LAG(order_item_count) OVER (ORDER BY year) IS NULL
                 OR LAG(order_item_count) OVER (ORDER BY year) = 0
            THEN NULL
            ELSE ROUND(
                (order_item_count - LAG(order_item_count) OVER (ORDER BY year))::numeric
                / LAG(order_item_count) OVER (ORDER BY year) * 100, 2)
        END AS yoy_order_item_count_pct,
        ROUND(product_sales,    2) AS ytd_product_sales,
        ROUND(freight_value,    2) AS ytd_freight_value,
        order_item_count            AS ytd_order_item_count
    FROM yearly_base
    ORDER BY year
    """
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
        return jsonify({'status': 'ok', 'level': 'year', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint 4: /api/olap/rollup — Roll-up Tháng → Quý → Năm → Grand Total
# ---------------------------------------------------------------------------
@app.route('/api/olap/rollup', methods=['GET'])
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
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
        return jsonify({'status': 'ok', 'operation': 'rollup', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint 5: /api/olap/timeanalysis — Phân tích thời gian thống nhất
# Hợp nhất Roll-up và Drill-down theo cấp người dùng chọn
# ---------------------------------------------------------------------------
@app.route('/api/olap/timeanalysis', methods=['GET'])
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

    elif level == 'month':
        # Grain: tháng — tạo chuỗi liên tục, NULL cho tháng thiếu
        # Xác định phạm vi tháng dựa theo filter
        if year:
            range_condition = f"d.year = {int(year)}"
            if quarter:
                range_condition += f" AND d.quarter = {int(quarter)}"
            series_sql = f"""
            SELECT
                EXTRACT(YEAR  FROM gs)::int AS year,
                EXTRACT(MONTH FROM gs)::int AS month
            FROM generate_series(
                (SELECT DATE_TRUNC('month', MIN(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)
                   AND year = {int(year)} {'AND quarter = ' + quarter if quarter else ''}),
                (SELECT DATE_TRUNC('month', MAX(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)
                   AND year = {int(year)} {'AND quarter = ' + quarter if quarter else ''}),
                INTERVAL '1 month'
            ) AS gs
            """
        else:
            series_sql = """
            SELECT
                EXTRACT(YEAR  FROM gs)::int AS year,
                EXTRACT(MONTH FROM gs)::int AS month
            FROM generate_series(
                (SELECT DATE_TRUNC('month', MIN(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
                (SELECT DATE_TRUNC('month', MAX(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
                INTERVAL '1 month'
            ) AS gs
            """

        # Tổng hợp thực tế (có filter)
        raw_where_parts = ["fco.order_status = 'delivered'"]
        if year:    raw_where_parts.append(f"d.year = {int(year)}")
        if quarter: raw_where_parts.append(f"d.quarter = {int(quarter)}")
        raw_where = "WHERE " + " AND ".join(raw_where_parts)

        sql = f"""
        WITH
        raw_data AS (
            SELECT d.year, d.month,
                SUM(fs.price)         AS product_sales,
                SUM(fs.freight_value) AS freight_value,
                COUNT(*)              AS order_item_count
            FROM dw.fact_sales fs
            JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
            JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
            {raw_where}
            GROUP BY d.year, d.month
        ),
        month_series AS (
            {series_sql}
        ),
        base AS (
            SELECT
                ms.year, ms.month,
                rd.product_sales,
                rd.freight_value,
                rd.order_item_count
            FROM month_series ms
            LEFT JOIN raw_data rd ON rd.year = ms.year AND rd.month = ms.month
        )
        SELECT
            year, month,
            ROUND(product_sales,    2) AS product_sales,
            ROUND(freight_value,    2) AS freight_value,
            order_item_count,
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
            END AS mom_order_item_count_pct
        FROM base
        ORDER BY year, month
        """

    elif level == 'quarter':
        raw_where_parts = ["fco.order_status = 'delivered'"]
        if year: raw_where_parts.append(f"d.year = {int(year)}")
        raw_where = "WHERE " + " AND ".join(raw_where_parts)

        if year:
            series_sql = f"""
            SELECT
                EXTRACT(YEAR    FROM gs)::int AS year,
                EXTRACT(QUARTER FROM gs)::int AS quarter
            FROM generate_series(
                (SELECT DATE_TRUNC('quarter', MIN(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)
                   AND year = {int(year)}),
                (SELECT DATE_TRUNC('quarter', MAX(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)
                   AND year = {int(year)}),
                INTERVAL '3 months'
            ) AS gs
            """
        else:
            series_sql = """
            SELECT
                EXTRACT(YEAR    FROM gs)::int AS year,
                EXTRACT(QUARTER FROM gs)::int AS quarter
            FROM generate_series(
                (SELECT DATE_TRUNC('quarter', MIN(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
                (SELECT DATE_TRUNC('quarter', MAX(full_date)) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
                INTERVAL '3 months'
            ) AS gs
            """

        sql = f"""
        WITH
        raw_data AS (
            SELECT d.year, d.quarter,
                SUM(fs.price)         AS product_sales,
                SUM(fs.freight_value) AS freight_value,
                COUNT(*)              AS order_item_count
            FROM dw.fact_sales fs
            JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
            JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
            {raw_where}
            GROUP BY d.year, d.quarter
        ),
        qtr_series AS (
            {series_sql}
        ),
        base AS (
            SELECT
                qs.year, qs.quarter,
                rd.product_sales,
                rd.freight_value,
                rd.order_item_count
            FROM qtr_series qs
            LEFT JOIN raw_data rd ON rd.year = qs.year AND rd.quarter = qs.quarter
        )
        SELECT
            year, quarter,
            ROUND(product_sales,    2) AS product_sales,
            ROUND(freight_value,    2) AS freight_value,
            order_item_count,
            CASE
                WHEN product_sales IS NULL OR LAG(product_sales) OVER (ORDER BY year, quarter) IS NULL
                     OR LAG(product_sales) OVER (ORDER BY year, quarter) = 0
                THEN NULL
                ELSE ROUND(
                    (product_sales - LAG(product_sales) OVER (ORDER BY year, quarter))
                    / LAG(product_sales) OVER (ORDER BY year, quarter) * 100, 2)
            END AS qoq_product_sales_pct,
            CASE
                WHEN freight_value IS NULL OR LAG(freight_value) OVER (ORDER BY year, quarter) IS NULL
                     OR LAG(freight_value) OVER (ORDER BY year, quarter) = 0
                THEN NULL
                ELSE ROUND(
                    (freight_value - LAG(freight_value) OVER (ORDER BY year, quarter))
                    / LAG(freight_value) OVER (ORDER BY year, quarter) * 100, 2)
            END AS qoq_freight_value_pct,
            CASE
                WHEN order_item_count IS NULL OR LAG(order_item_count) OVER (ORDER BY year, quarter) IS NULL
                     OR LAG(order_item_count) OVER (ORDER BY year, quarter) = 0
                THEN NULL
                ELSE ROUND(
                    (order_item_count - LAG(order_item_count) OVER (ORDER BY year, quarter))::numeric
                    / LAG(order_item_count) OVER (ORDER BY year, quarter) * 100, 2)
            END AS qoq_order_item_count_pct
        FROM base
        ORDER BY year, quarter
        """

    else:  # level == 'year'
        sql = """
        WITH
        yearly_raw AS (
            SELECT d.year,
                SUM(fs.price)         AS product_sales,
                SUM(fs.freight_value) AS freight_value,
                COUNT(*)              AS order_item_count
            FROM dw.fact_sales fs
            JOIN dw.dim_date d         ON fs.purchase_date_key = d.date_key
            JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
            WHERE fco.order_status = 'delivered'
            GROUP BY d.year
        ),
        year_series AS (
            SELECT generate_series(
                (SELECT MIN(year) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales)),
                (SELECT MAX(year) FROM dw.dim_date
                 WHERE date_key IN (SELECT purchase_date_key FROM dw.fact_sales))
            )::int AS year
        ),
        base AS (
            SELECT ys.year, yr.product_sales, yr.freight_value, yr.order_item_count
            FROM year_series ys
            LEFT JOIN yearly_raw yr USING (year)
        )
        SELECT
            year,
            ROUND(product_sales,    2) AS product_sales,
            ROUND(freight_value,    2) AS freight_value,
            order_item_count,
            CASE
                WHEN product_sales IS NULL OR LAG(product_sales) OVER (ORDER BY year) IS NULL
                     OR LAG(product_sales) OVER (ORDER BY year) = 0
                THEN NULL
                ELSE ROUND(
                    (product_sales - LAG(product_sales) OVER (ORDER BY year))
                    / LAG(product_sales) OVER (ORDER BY year) * 100, 2)
            END AS yoy_product_sales_pct,
            CASE
                WHEN freight_value IS NULL OR LAG(freight_value) OVER (ORDER BY year) IS NULL
                     OR LAG(freight_value) OVER (ORDER BY year) = 0
                THEN NULL
                ELSE ROUND(
                    (freight_value - LAG(freight_value) OVER (ORDER BY year))
                    / LAG(freight_value) OVER (ORDER BY year) * 100, 2)
            END AS yoy_freight_value_pct,
            CASE
                WHEN order_item_count IS NULL OR LAG(order_item_count) OVER (ORDER BY year) IS NULL
                     OR LAG(order_item_count) OVER (ORDER BY year) = 0
                THEN NULL
                ELSE ROUND(
                    (order_item_count - LAG(order_item_count) OVER (ORDER BY year))::numeric
                    / LAG(order_item_count) OVER (ORDER BY year) * 100, 2)
            END AS yoy_order_item_count_pct
        FROM base
        ORDER BY year
        """

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
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
@app.route('/api/olap/drilldown', methods=['GET'])
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
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
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
@app.route('/api/olap/slice', methods=['GET'])
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
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
        return jsonify({'status': 'ok', 'operation': 'slice',
                        'filters': {'year': y}, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint 8: /api/olap/dice — Chọn tập con đa điều kiện
# Khi có weekend filter: trả từng ngày (full_date) kèm is_weekend
# ---------------------------------------------------------------------------
@app.route('/api/olap/dice', methods=['GET'])
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
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
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
@app.route('/api/olap/pivot', methods=['GET'])
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
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            data = _rows_to_dicts(cur)
        conn.close()
        return jsonify({'status': 'ok', 'operation': 'pivot',
                        'kpi': kpi, 'type': ptype, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint tổng hợp: /api/olap — Routing theo time_level và operation
# ---------------------------------------------------------------------------
@app.route('/api/olap', methods=['GET'])
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

    with app.test_request_context():
        pass

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


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'db': str(e)}), 500


if __name__ == '__main__':
    print("Starting OLAP Sales & Time API on http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=True)
