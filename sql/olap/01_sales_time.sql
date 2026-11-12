-- =============================================================================
-- FILE: sql/olap/01_sales_time.sql
-- CHỦ ĐỀ: Sales & Time — Doanh thu và xu hướng theo thời gian
-- DATABASE: olist_dw  |  SCHEMA: dw
-- =============================================================================
-- Các bảng sử dụng:
--   dw.fact_sales           grain: (order_id, order_item_id)  — price, freight_value
--   dw.fact_customer_order  grain: order_id                   — order_status
--   dw.dim_date             — date_key, year, quarter, month,
--                             day_of_month, day_of_week, is_weekend, full_date
--
-- Phạm vi đơn hàng: order_status = 'delivered'
--
-- KPI chính:
--   product_sales    = SUM(fs.price)
--   freight_value    = SUM(fs.freight_value)
--   order_item_count = COUNT(*)   (số dòng sản phẩm, không phải số đơn)
--
-- Không join bảng thanh toán trực tiếp vào fact_sales để tránh nhân bản dòng.
-- =============================================================================


-- =============================================================================
-- PHẦN 0: VIEW TIỆN ÍCH — Dữ liệu delivered, dùng chung cho các truy vấn
-- =============================================================================
CREATE OR REPLACE VIEW dw.v_sales_delivered AS
SELECT
    fs.order_id,
    fs.order_item_id,
    fs.purchase_date_key,
    fs.price,
    fs.freight_value,
    d.year,
    d.quarter,
    d.month,
    d.day_of_month,
    d.day_of_week,
    d.is_weekend,
    d.full_date
FROM dw.fact_sales fs
JOIN dw.dim_date d
    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco
    ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered';


-- =============================================================================
-- PHẦN 1: TỔNG HỢP THEO THÁNG — KPI + MoM Growth + YTD
-- =============================================================================
-- Logic:
--   1. Tổng hợp theo (year, month) với bộ lọc delivered.
--   2. Tạo chuỗi tháng liên tục trong phạm vi dữ liệu.
--   3. LEFT JOIN → tháng không có giao dịch giữ NULL (không gán 0), ví dụ 2016-11.
--   4. LAG() trên chuỗi đầy đủ → tháng trước là tháng lịch liền trước.
--   5. MoM Growth với NULLIF để tránh chia 0.
--   6. YTD bằng SUM() OVER (PARTITION BY year ORDER BY month) — reset mỗi năm.

WITH
monthly_raw AS (
    SELECT
        d.year,
        d.month,
        SUM(fs.price)         AS product_sales,
        SUM(fs.freight_value) AS freight_value,
        COUNT(*)              AS order_item_count
    FROM dw.fact_sales fs
    JOIN dw.dim_date d
        ON fs.purchase_date_key = d.date_key
    JOIN dw.fact_customer_order fco
        ON fs.order_id = fco.order_id
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

-- NULL (không dùng COALESCE=0) để phân biệt tháng thực sự không có giao dịch
-- với tháng bị thiếu dữ liệu chưa xác minh.
monthly_base AS (
    SELECT
        ms.year,
        ms.month,
        mr.product_sales,       -- NULL nếu LEFT JOIN không khớp
        mr.freight_value,
        mr.order_item_count
    FROM month_series ms
    LEFT JOIN monthly_raw mr
        ON mr.year = ms.year AND mr.month = ms.month
),

monthly_with_metrics AS (
    SELECT
        year,
        month,
        product_sales,
        freight_value,
        order_item_count,

        -- MoM Growth: NULL nếu tháng hiện tại hoặc tháng trước NULL, hoặc tháng trước = 0
        CASE
            WHEN product_sales IS NULL
              OR LAG(product_sales) OVER (ORDER BY year, month) IS NULL
              OR LAG(product_sales) OVER (ORDER BY year, month) = 0
            THEN NULL
            ELSE ROUND(
                (product_sales - LAG(product_sales) OVER (ORDER BY year, month))
                / LAG(product_sales) OVER (ORDER BY year, month) * 100, 2)
        END AS mom_product_sales_pct,

        CASE
            WHEN freight_value IS NULL
              OR LAG(freight_value) OVER (ORDER BY year, month) IS NULL
              OR LAG(freight_value) OVER (ORDER BY year, month) = 0
            THEN NULL
            ELSE ROUND(
                (freight_value - LAG(freight_value) OVER (ORDER BY year, month))
                / LAG(freight_value) OVER (ORDER BY year, month) * 100, 2)
        END AS mom_freight_value_pct,

        CASE
            WHEN order_item_count IS NULL
              OR LAG(order_item_count) OVER (ORDER BY year, month) IS NULL
              OR LAG(order_item_count) OVER (ORDER BY year, month) = 0
            THEN NULL
            ELSE ROUND(
                (order_item_count - LAG(order_item_count) OVER (ORDER BY year, month))::numeric
                / LAG(order_item_count) OVER (ORDER BY year, month) * 100, 2)
        END AS mom_order_item_count_pct,

        -- YTD: SUM bỏ qua NULL tự nhiên (PostgreSQL SUM ignores NULLs)
        SUM(product_sales)    OVER (PARTITION BY year ORDER BY month) AS ytd_product_sales,
        SUM(freight_value)    OVER (PARTITION BY year ORDER BY month) AS ytd_freight_value,
        SUM(order_item_count) OVER (PARTITION BY year ORDER BY month) AS ytd_order_item_count

    FROM monthly_base
)

SELECT
    year,
    month,
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
ORDER BY year, month;


-- =============================================================================
-- PHẦN 2 + 3: TĂNG TRƯỞNG QUÝ (QoQ) VÀ NĂM (YoY) — SO SÁNH CÙNG KỲ
-- =============================================================================
-- Vì sao không lấy tổng cả kỳ chia tổng cả kỳ trước:
--   Dữ liệu delivered chỉ phủ 2016-09..2018-08 và thiếu 2016-11. Năm 2016 có 3 tháng,
--   năm 2018 có 8 tháng, quý 3/2018 có 2 tháng. Chia tổng cả kỳ thì tỷ lệ lẫn chênh lệch
--   số tháng vào tăng trưởng:
--     2018 (T1–T8) / 2017 (T1–T12)  = +21%   ← sai bản chất
--     2018 (T1–T8) / 2017 (T1–T8)   = +141%  ← cùng kỳ
--     Q3/2018 (2 tháng) / Q2/2018   ≈ −39%   ← chỉ vì thiếu tháng 9
--
-- Quy tắc cùng kỳ (like-for-like):
--   YoY(Y) = Σ_{m∈M} X(Y,m) / Σ_{m∈M} X(Y−1,m) − 1,   M = tháng lịch có dữ liệu ở cả Y và Y−1
--   QoQ(q) = như trên, ghép tháng thứ k của quý q với tháng thứ k của quý liền trước
-- Tổng của kỳ vẫn là tổng đầy đủ. months_with_data / months_compared / is_partial cho người đọc
-- biết tỷ lệ được tính trên bao nhiêu tháng.
-- Cùng logic với backend/app/features/sales_time/growth.py (API màn Thời gian).

-- 2. Theo quý
WITH
monthly AS (
    SELECT d.year, d.quarter, d.month,
           SUM(fs.price)         AS product_sales,
           SUM(fs.freight_value) AS freight_value,
           COUNT(*)              AS order_item_count
    FROM dw.fact_sales fs
    JOIN dw.dim_date d              ON fs.purchase_date_key = d.date_key
    JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
    WHERE fco.order_status = 'delivered'
    GROUP BY d.year, d.quarter, d.month
),
period AS (
    SELECT year, quarter,
           SUM(product_sales) AS product_sales,
           SUM(freight_value) AS freight_value,
           SUM(order_item_count) AS order_item_count,
           COUNT(*) AS months_with_data
    FROM monthly
    GROUP BY year, quarter
),
same_period AS (
    SELECT cur.year, cur.quarter,
           SUM(cur.product_sales)     AS cur_sales,   SUM(prev.product_sales)     AS prev_sales,
           SUM(cur.freight_value)     AS cur_freight, SUM(prev.freight_value)     AS prev_freight,
           SUM(cur.order_item_count)  AS cur_items,   SUM(prev.order_item_count)  AS prev_items,
           COUNT(*) AS months_compared
    FROM monthly cur
    JOIN monthly prev
      ON prev.year * 4 + prev.quarter = cur.year * 4 + cur.quarter - 1   -- quý liền trước
     AND mod(prev.month - 1, 3) = mod(cur.month - 1, 3)                  -- cùng vị trí tháng trong quý
    GROUP BY cur.year, cur.quarter
)
SELECT
    p.year,
    p.quarter,
    ROUND(p.product_sales, 2) AS product_sales,
    ROUND(p.freight_value, 2) AS freight_value,
    p.order_item_count,
    ROUND((s.cur_sales   - s.prev_sales)   / NULLIF(s.prev_sales, 0)   * 100, 2) AS qoq_product_sales_pct,
    ROUND((s.cur_freight - s.prev_freight) / NULLIF(s.prev_freight, 0) * 100, 2) AS qoq_freight_value_pct,
    ROUND((s.cur_items   - s.prev_items)::numeric / NULLIF(s.prev_items, 0) * 100, 2) AS qoq_order_item_count_pct,
    p.months_with_data,
    COALESCE(s.months_compared, 0) AS months_compared,
    p.months_with_data < 3         AS is_partial
FROM period p
LEFT JOIN same_period s ON s.year = p.year AND s.quarter = p.quarter
ORDER BY p.year, p.quarter;


-- 3. Theo năm
WITH
monthly AS (
    SELECT d.year, d.month,
           SUM(fs.price)         AS product_sales,
           SUM(fs.freight_value) AS freight_value,
           COUNT(*)              AS order_item_count
    FROM dw.fact_sales fs
    JOIN dw.dim_date d              ON fs.purchase_date_key = d.date_key
    JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
    WHERE fco.order_status = 'delivered'
    GROUP BY d.year, d.month
),
period AS (
    SELECT year,
           SUM(product_sales) AS product_sales,
           SUM(freight_value) AS freight_value,
           SUM(order_item_count) AS order_item_count,
           COUNT(*) AS months_with_data
    FROM monthly
    GROUP BY year
),
same_period AS (
    SELECT cur.year,
           SUM(cur.product_sales)     AS cur_sales,   SUM(prev.product_sales)     AS prev_sales,
           SUM(cur.freight_value)     AS cur_freight, SUM(prev.freight_value)     AS prev_freight,
           SUM(cur.order_item_count)  AS cur_items,   SUM(prev.order_item_count)  AS prev_items,
           COUNT(*) AS months_compared
    FROM monthly cur
    JOIN monthly prev ON prev.year = cur.year - 1 AND prev.month = cur.month   -- cùng tháng năm trước
    GROUP BY cur.year
)
SELECT
    p.year,
    ROUND(p.product_sales, 2) AS product_sales,
    ROUND(p.freight_value, 2) AS freight_value,
    p.order_item_count,
    ROUND((s.cur_sales   - s.prev_sales)   / NULLIF(s.prev_sales, 0)   * 100, 2) AS yoy_product_sales_pct,
    ROUND((s.cur_freight - s.prev_freight) / NULLIF(s.prev_freight, 0) * 100, 2) AS yoy_freight_value_pct,
    ROUND((s.cur_items   - s.prev_items)::numeric / NULLIF(s.prev_items, 0) * 100, 2) AS yoy_order_item_count_pct,
    p.months_with_data,
    COALESCE(s.months_compared, 0) AS months_compared,
    p.months_with_data < 12        AS is_partial
FROM period p
LEFT JOIN same_period s ON s.year = p.year
ORDER BY p.year;


-- =============================================================================
-- PHẦN 4: ROLL-UP — Tháng → Quý → Năm → Grand Total
-- =============================================================================
-- GROUP BY ROLLUP sinh subtotal ở từng cấp và grand total cuối cùng.
-- GROUPING() phân biệt NULL do ROLLUP với NULL thực tế trong dữ liệu.
-- grouping_level: 0=chi tiết tháng, 1=subtotal quý, 3=subtotal năm, 7=grand total

SELECT
    CASE WHEN GROUPING(d.year)    = 1 THEN 'GRAND TOTAL' ELSE d.year::text    END AS year_label,
    CASE WHEN GROUPING(d.quarter) = 1 THEN 'All Qtrs'   ELSE d.quarter::text  END AS quarter_label,
    CASE WHEN GROUPING(d.month)   = 1 THEN 'All Months'  ELSE d.month::text   END AS month_label,

    GROUPING(d.year, d.quarter, d.month) AS grouping_level,

    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count

FROM dw.fact_sales fs
JOIN dw.dim_date d
    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco
    ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
GROUP BY ROLLUP(d.year, d.quarter, d.month)
ORDER BY
    d.year    NULLS LAST,
    d.quarter NULLS LAST,
    d.month   NULLS LAST;


-- =============================================================================
-- PHẦN 5: DRILL-DOWN — Từ tổng quan xuống chi tiết theo thời gian
-- =============================================================================

-- Bước 1: Tổng theo Năm
SELECT
    d.year,
    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count
FROM dw.fact_sales fs
JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
GROUP BY d.year
ORDER BY d.year;

-- Bước 2: Drill-down vào 1 năm → theo Quý   (thay 2017 bằng năm cần xem)
SELECT
    d.year,
    d.quarter,
    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count
FROM dw.fact_sales fs
JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.year = 2017
GROUP BY d.year, d.quarter
ORDER BY d.quarter;

-- Bước 3: Drill-down vào 1 quý → theo Tháng
SELECT
    d.year,
    d.quarter,
    d.month,
    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count
FROM dw.fact_sales fs
JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.year = 2017
  AND d.quarter = 3
GROUP BY d.year, d.quarter, d.month
ORDER BY d.month;

-- Bước 4: Drill-down vào 1 tháng → theo Ngày
SELECT
    d.year,
    d.month,
    d.day_of_month,
    d.full_date,
    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count
FROM dw.fact_sales fs
JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.year  = 2017
  AND d.month = 9
GROUP BY d.year, d.month, d.day_of_month, d.full_date
ORDER BY d.full_date;

-- Bước 5: Phân tích theo is_weekend — grain=NGÀY để không gộp nhiều ngày thành 1 cột
-- Group theo full_date + is_weekend: mỗi ngày là 1 hàng, is_weekend dùng để phân loại/lọc
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
JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.year  = 2017
  AND d.month = 9
  -- Lọc cuối tuần hoặc ngày thường tùy yêu cầu:
  -- AND d.is_weekend = TRUE   -- chỉ cuối tuần
  -- AND d.is_weekend = FALSE  -- chỉ ngày thường
GROUP BY d.year, d.month, d.day_of_month, d.full_date, d.is_weekend
ORDER BY d.full_date;


-- =============================================================================
-- PHẦN 6: SLICE — Cố định một chiều, phân tích tập dữ liệu con
-- =============================================================================
-- Ví dụ: Slice year = 2017, xem KPI theo tháng kèm MoM (so tháng liền trước, vốn đã cùng độ dài).
-- Tháng 1/2017 cần tháng 12/2016 làm kỳ tham chiếu → lấy thêm nhưng không hiển thị.

WITH
monthly_raw AS (
    SELECT
        d.year,
        d.month,
        SUM(fs.price)         AS product_sales,
        SUM(fs.freight_value) AS freight_value,
        COUNT(*)              AS order_item_count
    FROM dw.fact_sales fs
    JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
    JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
    WHERE fco.order_status = 'delivered'
      AND (d.year = 2017 OR (d.year = 2016 AND d.month = 12))
    GROUP BY d.year, d.month
),

month_series AS (
    SELECT s_year AS year, s_month AS month
    FROM (
        SELECT 2016 AS s_year, 12 AS s_month
        UNION ALL
        SELECT 2017, generate_series(1, 12)
    ) t
),

-- NULL thay COALESCE=0 để phân biệt tháng không có giao dịch với tháng thiếu dữ liệu
slice_base AS (
    SELECT
        ms.year,
        ms.month,
        mr.product_sales,       -- NULL nếu tháng không có giao dịch
        mr.freight_value,
        mr.order_item_count
    FROM month_series ms
    LEFT JOIN monthly_raw mr USING (year, month)
),

slice_with_metrics AS (
    SELECT
        year,
        month,
        product_sales,
        freight_value,
        order_item_count,

        CASE
            WHEN product_sales IS NULL
              OR LAG(product_sales) OVER (ORDER BY year, month) IS NULL
              OR LAG(product_sales) OVER (ORDER BY year, month) = 0
            THEN NULL
            ELSE ROUND(
                (product_sales - LAG(product_sales) OVER (ORDER BY year, month))
                / LAG(product_sales) OVER (ORDER BY year, month) * 100, 2)
        END AS mom_product_sales_pct,

        CASE
            WHEN freight_value IS NULL
              OR LAG(freight_value) OVER (ORDER BY year, month) IS NULL
              OR LAG(freight_value) OVER (ORDER BY year, month) = 0
            THEN NULL
            ELSE ROUND(
                (freight_value - LAG(freight_value) OVER (ORDER BY year, month))
                / LAG(freight_value) OVER (ORDER BY year, month) * 100, 2)
        END AS mom_freight_value_pct,

        CASE
            WHEN order_item_count IS NULL
              OR LAG(order_item_count) OVER (ORDER BY year, month) IS NULL
              OR LAG(order_item_count) OVER (ORDER BY year, month) = 0
            THEN NULL
            ELSE ROUND(
                (order_item_count - LAG(order_item_count) OVER (ORDER BY year, month))::numeric
                / LAG(order_item_count) OVER (ORDER BY year, month) * 100, 2)
        END AS mom_order_item_count_pct,

        -- YTD: SUM bỏ qua NULL tự nhiên
        SUM(product_sales)    OVER (PARTITION BY year ORDER BY month) AS ytd_product_sales,
        SUM(freight_value)    OVER (PARTITION BY year ORDER BY month) AS ytd_freight_value,
        SUM(order_item_count) OVER (PARTITION BY year ORDER BY month) AS ytd_order_item_count
    FROM slice_base
)

SELECT
    year,
    month,
    ROUND(product_sales,    2) AS product_sales,
    ROUND(freight_value,    2) AS freight_value,
    order_item_count,
    mom_product_sales_pct,
    mom_freight_value_pct,
    mom_order_item_count_pct,
    ROUND(ytd_product_sales,    2) AS ytd_product_sales,
    ROUND(ytd_freight_value,    2) AS ytd_freight_value,
    ytd_order_item_count
FROM slice_with_metrics
WHERE year = 2017        -- << chỉ hiển thị năm đã Slice; kỳ tham chiếu đã dùng xong
ORDER BY month;


-- =============================================================================
-- PHẦN 7: DICE — Chọn tập con bằng nhiều điều kiện đồng thời
-- =============================================================================
-- Grain quan trọng: khi lọc is_weekend, phải group theo full_date (grain=ngày)
-- để KHÔNG gộp tất cả ngày cuối tuần trong quý thành 1 cột duy nhất.

-- Dice ví dụ 1: quý 4 + cuối tuần → hiển thị từng ngày
SELECT
    d.year,
    d.quarter,
    d.month,
    d.full_date,
    d.is_weekend,
    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count
FROM dw.fact_sales fs
JOIN dw.dim_date d
    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco
    ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.quarter    = 4           -- điều kiện Dice 1: quý 4
  AND d.is_weekend = TRUE        -- điều kiện Dice 2: cuối tuần
GROUP BY d.year, d.quarter, d.month, d.full_date, d.is_weekend
ORDER BY d.full_date;

-- Dice ví dụ 2: đa chiều, hiển thị theo ngày (grain=ngày giữ đúng is_weekend)
SELECT
    d.year,
    d.quarter,
    d.month,
    d.full_date,
    d.is_weekend,
    ROUND(SUM(fs.price),         2) AS product_sales,
    ROUND(SUM(fs.freight_value), 2) AS freight_value,
    COUNT(*)                        AS order_item_count
FROM dw.fact_sales fs
JOIN dw.dim_date d
    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco
    ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.quarter    = 4
  AND d.is_weekend = TRUE
  AND d.year BETWEEN 2016 AND 2018
GROUP BY d.year, d.quarter, d.month, d.full_date, d.is_weekend
ORDER BY d.full_date;


-- =============================================================================
-- PHẦN 8: PIVOT — Ma trận Tháng x Năm cho Product Sales và MoM Growth
-- =============================================================================

-- 8a. Ma trận Product Sales theo Tháng x Năm
SELECT
    d.month,
    ROUND(SUM(fs.price) FILTER (WHERE d.year = 2016), 2) AS sales_2016,
    ROUND(SUM(fs.price) FILTER (WHERE d.year = 2017), 2) AS sales_2017,
    ROUND(SUM(fs.price) FILTER (WHERE d.year = 2018), 2) AS sales_2018
FROM dw.fact_sales fs
JOIN dw.dim_date d
    ON fs.purchase_date_key = d.date_key
JOIN dw.fact_customer_order fco
    ON fs.order_id = fco.order_id
WHERE fco.order_status = 'delivered'
  AND d.year IN (2016, 2017, 2018)
GROUP BY d.month
ORDER BY d.month;


-- 8b. Ma trận MoM Growth theo Tháng x Năm
-- Tính MoM riêng trong từng năm, sau đó pivot kết quả
WITH
monthly_all AS (
    SELECT
        d.year,
        d.month,
        SUM(fs.price) AS product_sales
    FROM dw.fact_sales fs
    JOIN dw.dim_date d    ON fs.purchase_date_key = d.date_key
    JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
    WHERE fco.order_status = 'delivered'
    GROUP BY d.year, d.month
),

month_year_series AS (
    SELECT y, m
    FROM generate_series(2016, 2018) AS y,
         generate_series(1, 12)      AS m
),

-- Giữ NULL cho tháng không có giao dịch (2016-01..08, 2016-11, 2018-09..12). Gán 0 sẽ sinh
-- MoM = −100% giả ở tháng dữ liệu kết thúc và NULL ở tháng kế tiếp, lẫn với sụt giảm thật.
full_base AS (
    SELECT
        mys.y   AS year,
        mys.m   AS month,
        ma.product_sales
    FROM month_year_series mys
    LEFT JOIN monthly_all ma
        ON ma.year = mys.y AND ma.month = mys.m
),

-- MoM tính trong phạm vi từng năm (không so sánh tháng 12 năm trước sang tháng 1)
mom_per_year AS (
    SELECT
        year,
        month,
        ROUND(
            (product_sales - LAG(product_sales) OVER (PARTITION BY year ORDER BY month))
            / NULLIF(LAG(product_sales) OVER (PARTITION BY year ORDER BY month), 0) * 100,
        2) AS mom_pct
    FROM full_base
)

SELECT
    month,
    MAX(CASE WHEN year = 2016 THEN mom_pct END) AS mom_2016_pct,
    MAX(CASE WHEN year = 2017 THEN mom_pct END) AS mom_2017_pct,
    MAX(CASE WHEN year = 2018 THEN mom_pct END) AS mom_2018_pct
FROM mom_per_year
GROUP BY month
ORDER BY month;
