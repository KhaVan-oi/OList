-- =============================================================================
-- FILE: sql/olap/03_customer_payment.sql
-- CHỦ ĐỀ: Bạn 3 — Customer / Payment & Behavioral Profiling (Hành vi thanh toán & Phân tích khách hàng)
-- DATABASE: olist_dw  |  SCHEMA: dw (Chỉ đọc dw, không sửa staging/schema kho)
-- =============================================================================
-- Các bảng sử dụng:
--   dw.fact_customer_order  grain: order_id            — order_status, total_payment_value,
--                                                        customer_state, customer_city,
--                                                        purchase_date_key, approved_date_key
--   dw.dim_customer         grain: customer_key        — customer_unique_id
--   dw.dim_date             grain: date_key (YYYYMMDD) — full_date, year, quarter, month,
--                                                        day_of_week, is_weekend
--
-- Chốt phạm vi số liệu với Bạn 1 và Bạn 2:
--   1. Đơn tính doanh thu / chi tiêu (Monetary) / AOV / Repeat Rate:
--      CHỈ lấy đơn có `order_status = 'delivered'` (96,478 đơn của 93,358 khách hàng).
--      (Lưu ý: Toàn bộ mô hình phân khúc RFM, thuật toán K-Means Clustering, kịch bản What-if
--       và khuyến nghị chiến lược được hiện thực trọn vẹn trong Giai đoạn 5 - DSS).
--   2. Phân biệt chỉ số tiền giữa 2 Fact:
--      - Bạn 1 & Bạn 2 đọc `dw.fact_sales`: tính Doanh thu hàng hóa = `SUM(price)` (13,221,498.11 R$)
--        và Cước vận chuyển = `SUM(freight_value)` (2,198,266.93 R$).
--      - Bạn 3 đọc `dw.fact_customer_order`: tính Giá trị thanh toán đơn hàng đã giao
--        (`delivered_payment_value` / `Monetary`) = `SUM(total_payment_value)` (15,422,461.77 R$,
--        đã gồm tiền hàng + cước vận chuyển) và `AOV` = `AVG(total_payment_value)` (159.86 R$).
--   3. Mốc thời gian: gắn theo `purchase_date_key` (ngày khách đặt hàng).
--   4. Phá hòa (Tie-breaking): mọi câu xếp hạng và Window Function (`DENSE_RANK`, `PERCENT_RANK`)
--      đều có khóa phụ đến tận `customer_unique_id` hoặc `customer_state`
--      để kết quả cố định 100% giữa mọi lần chạy.
-- =============================================================================

DROP VIEW IF EXISTS valid_customer_orders;

CREATE TEMP VIEW valid_customer_orders AS
SELECT
    f.order_id,
    f.customer_key,
    c.customer_unique_id,
    f.purchase_date_key,
    f.approved_date_key,
    f.order_status,
    f.total_payment_value                         AS raw_payment_value,
    COALESCE(f.total_payment_value, 0::numeric)   AS payment_value,
    f.customer_state,
    f.customer_city,
    d.full_date                                   AS purchase_date,
    d.year,
    d.quarter,
    d.month,
    d.is_weekend
FROM dw.fact_customer_order AS f
JOIN dw.dim_customer AS c
    ON c.customer_key = f.customer_key
JOIN dw.dim_date AS d
    ON d.date_key = f.purchase_date_key
WHERE f.order_status = 'delivered';


-- =============================================================================
-- 0) Kiểm tra nền (valid_customer_orders):
--    Tổng khách hàng delivered / tổng số đơn delivered / tổng thanh toán (Monetary) / AOV
-- =============================================================================
SELECT
    count(DISTINCT customer_unique_id) AS delivered_customers,
    count(order_id)                    AS delivered_orders,
    round(sum(payment_value), 2)       AS delivered_payment_value,
    round(avg(raw_payment_value), 2)   AS delivered_aov
FROM valid_customer_orders;


-- =============================================================================
-- 1) KPI Tỷ lệ khách hàng quay lại mua hàng (Repeat Customer Rate) & ARPU
--    Chỉ tính trên đơn delivered: khách quay lại có count(order_id) > 1
-- =============================================================================
WITH customer_summary AS (
    SELECT
        customer_unique_id,
        count(order_id)              AS order_count,
        sum(payment_value)           AS total_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
)
SELECT
    count(*)                                                                 AS delivered_customers,
    count(*) FILTER (WHERE order_count = 1)                                  AS one_time_customers,
    count(*) FILTER (WHERE order_count > 1)                                  AS repeat_customers,
    round(100.0 * count(*) FILTER (WHERE order_count > 1) / count(*), 2)     AS repeat_customer_rate_pct,
    round(sum(total_spend), 2)                                               AS total_monetary_value,
    round(avg(total_spend), 2)                                               AS avg_monetary_per_customer
FROM customer_summary;


-- =============================================================================
-- 2) KPI Tỷ lệ hủy đơn / giao thành công theo trạng thái `order_status`
--    Đọc toàn bộ dw.fact_customer_order để lấy tỷ lệ 8 trạng thái đơn,
--    nhưng cột `delivered_payment_value` và `delivered_aov` CHỈ ghi nhận cho 'delivered'
-- =============================================================================
SELECT
    f.order_status,
    count(f.order_id)                                                        AS orders,
    count(DISTINCT f.customer_key)                                           AS unique_customers,
    round(100.0 * count(f.order_id) / sum(count(f.order_id)) OVER (), 2)     AS pct_orders,
    round(
        sum(CASE WHEN f.order_status = 'delivered' THEN coalesce(f.total_payment_value, 0) ELSE 0 END),
        2
    )                                                                        AS delivered_payment_value,
    round(
        avg(CASE WHEN f.order_status = 'delivered' THEN f.total_payment_value END),
        2
    )                                                                        AS delivered_aov,
    round(avg(da.full_date - dp.full_date), 2)                               AS avg_approval_delay_days
FROM dw.fact_customer_order AS f
JOIN dw.dim_date AS dp
    ON dp.date_key = f.purchase_date_key
LEFT JOIN dw.dim_date AS da
    ON da.date_key = f.approved_date_key
GROUP BY f.order_status
ORDER BY count(f.order_id) DESC, f.order_status ASC;


-- =============================================================================
-- 3) KPI Số khách hàng, số đơn, tổng giá trị thanh toán và AOV theo Bang
--    Chỉ tính trên đơn delivered (`valid_customer_orders`)
-- =============================================================================
SELECT
    customer_state,
    count(DISTINCT customer_unique_id) AS delivered_customers,
    count(order_id)                    AS delivered_orders,
    round(sum(payment_value), 2)       AS delivered_payment_value,
    round(avg(raw_payment_value), 2)   AS delivered_aov
FROM valid_customer_orders
GROUP BY customer_state
ORDER BY sum(payment_value) DESC, count(order_id) DESC, customer_state ASC;


-- =============================================================================
-- 4a) ROLL-UP (Chiều Khách hàng): Cuộn từ mức chi tiết dọc theo Concept Hierarchy
--     Bậc tần suất (1, 2, 3, >=4 đơn) -> Nhóm khách (Mua 1 lần vs Mua lặp lại) -> Toàn bộ khách hàng delivered
--     Tuân thủ lý thuyết Concept Hierarchy trong phạm vi MỘT CHIỀU DUY NHẤT (Single Dimension):
--     Concept Hierarchy của Chiều Khách hàng (Chapter 2-cont Slide 15-16, 23 & Chapter 3 Slide 24):
--     grouping_level: 0 = Chi tiết bậc tần suất, 1 = Subtotal theo nhóm khách, 3 = Grand Total toàn bộ
-- =============================================================================
WITH customer_behavior AS (
    SELECT
        customer_unique_id,
        count(order_id)              AS order_count,
        sum(payment_value)           AS total_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
labeled_customers AS (
    SELECT
        customer_unique_id,
        order_count,
        total_spend,
        CASE
            WHEN order_count = 1 THEN '1. One-time Buyer (Mua 1 lan)'
            ELSE '2. Repeat Buyer (Mua nhieu lan)'
        END AS buyer_group,
        CASE
            WHEN order_count = 1 THEN '1.1. Mua dung 1 don'
            WHEN order_count = 2 THEN '2.1. Mua 2 don'
            WHEN order_count = 3 THEN '2.2. Mua 3 don'
            ELSE '2.3. Mua tu 4 don tro len'
        END AS frequency_tier
    FROM customer_behavior
)
SELECT
    CASE
        WHEN grouping(buyer_group) = 1 THEN '(ALL DELIVERED CUSTOMERS)'
        ELSE buyer_group
    END                                                                      AS buyer_group,
    CASE
        WHEN grouping(frequency_tier) = 1 THEN '(GROUP SUBTOTAL)'
        ELSE frequency_tier
    END                                                                      AS frequency_tier,
    grouping(buyer_group)                                                    AS grouping_buyer_group,
    grouping(frequency_tier)                                                 AS grouping_frequency_tier,
    grouping(buyer_group, frequency_tier)                                    AS grouping_level,
    count(customer_unique_id)                                                AS customers,
    round(
        100.0 * count(customer_unique_id) / max(count(customer_unique_id)) OVER (),
        2
    )                                                                        AS pct_customers,
    sum(order_count)                                                         AS delivered_orders,
    round(sum(total_spend), 2)                                               AS delivered_payment_value,
    round(
        100.0 * sum(total_spend) / max(sum(total_spend)) OVER (),
        2
    )                                                                        AS pct_payment_value,
    round(sum(total_spend) / nullif(sum(order_count), 0), 2)                 AS group_delivered_aov,
    round(avg(total_spend), 2)                                               AS avg_monetary_per_customer
FROM labeled_customers
GROUP BY ROLLUP (buyer_group, frequency_tier)
ORDER BY
    grouping(buyer_group) ASC,
    buyer_group ASC,
    grouping(frequency_tier) ASC,
    frequency_tier ASC;


-- =============================================================================
-- 4b) ROLL-UP (Vận hành trạng thái đơn): Cuộn từ (Trạng thái đơn, Bang) -> Trạng thái đơn -> Toàn bộ
--     Cột `delivered_payment_value` chỉ cộng tiền của đơn `order_status = 'delivered'`
--     grouping_level: 0 = chi tiết (order_status, customer_state), 1 = Subtotal theo order_status, 3 = Grand Total
-- =============================================================================
SELECT
    CASE
        WHEN grouping(f.order_status) = 1 THEN '(ALL STATUSES)'
        ELSE f.order_status
    END                                                                      AS order_status,
    CASE
        WHEN grouping(f.customer_state) = 1 THEN '(ALL STATES)'
        ELSE coalesce(f.customer_state, '(NULL STATE)')
    END                                                                      AS customer_state,
    grouping(f.order_status)                                                 AS grouping_status,
    grouping(f.customer_state)                                               AS grouping_state,
    grouping(f.order_status, f.customer_state)                               AS grouping_level,
    count(f.order_id)                                                        AS total_orders,
    count(f.order_id) FILTER (WHERE f.order_status = 'delivered')            AS delivered_orders,
    round(
        coalesce(sum(f.total_payment_value) FILTER (WHERE f.order_status = 'delivered'), 0),
        2
    )                                                                        AS delivered_payment_value,
    round(
        avg(f.total_payment_value) FILTER (WHERE f.order_status = 'delivered'),
        2
    )                                                                        AS delivered_aov
FROM dw.fact_customer_order AS f
GROUP BY ROLLUP (f.order_status, f.customer_state)
ORDER BY
    grouping(f.order_status) ASC,
    f.order_status ASC,
    grouping(f.customer_state) ASC,
    count(f.order_id) DESC,
    f.customer_state ASC;


-- =============================================================================
-- 5) CUBE (Đơn delivered): Đa chiều 5 Bang lớn (SP, RJ, MG, RS, PR) × Năm (2016..2018)
--    grouping_level: 0 = (Bang, Năm), 1 = Subtotal theo Bang, 2 = Subtotal theo Năm, 3 = Grand Total
-- =============================================================================
SELECT
    CASE
        WHEN grouping(customer_state) = 1 THEN '(ALL 5 STATES)'
        ELSE customer_state
    END                                        AS customer_state,
    CASE
        WHEN grouping(year) = 1 THEN '(ALL YEARS)'
        ELSE year::text
    END                                        AS purchase_year,
    grouping(customer_state, year)             AS grouping_level,
    count(order_id)                            AS delivered_orders,
    count(DISTINCT customer_unique_id)         AS delivered_customers,
    round(sum(payment_value), 2)               AS delivered_payment_value,
    round(avg(raw_payment_value), 2)           AS delivered_aov
FROM valid_customer_orders
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
GROUP BY CUBE (customer_state, year)
ORDER BY
    grouping(customer_state) ASC,
    grouping(year) ASC,
    sum(payment_value) DESC,
    customer_state ASC,
    year ASC;


-- =============================================================================
-- 6a) DRILL-DOWN (Chiều Khách hàng): Đi từ Khái quát -> Chi tiết (Ngược hướng 100% với Roll-up 4a)
--     Dọc theo Concept Hierarchy của Chiều Khách hàng (Chapter 3 Slide 25):
--     Cấp 0 (Toàn bộ khách delivered) -> Cấp 1 (Mua 1 lần vs Mua lặp lại) -> Cấp 2 (Bậc 1, 2, 3, >= 4 đơn)
--     Mô tả hành trình tương tác khoan sâu phân tích của nhà quản trị:
--       - Bước 1 (Cấp 0): Tổng thể toàn bộ khách hàng delivered (93.358 khách, 15.422.461,77 R$, AOV 159,86 R$)
--       - Bước 2 (Cấp 1): Khoan sâu mổ xẻ nhóm Mua 1 lần (97,00%) vs Mua lặp lại (3,00%)
--       - Bước 3 (Cấp 2): Khoan sâu tiếp vào nội tại nhóm Mua lặp lại (2 đơn: 2.573 khách, 3 đơn: 181 khách, >=4 đơn: 47 khách)
-- =============================================================================
WITH customer_behavior AS (
    SELECT
        customer_unique_id,
        count(order_id)              AS order_count,
        sum(payment_value)           AS total_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
labeled_customers AS (
    SELECT
        customer_unique_id,
        order_count,
        total_spend,
        CASE
            WHEN order_count = 1 THEN '1. One-time Buyer (Mua 1 lan)'
            ELSE '2. Repeat Buyer (Mua nhieu lan)'
        END AS buyer_group,
        CASE
            WHEN order_count = 1 THEN '1.1. Mua dung 1 don'
            WHEN order_count = 2 THEN '2.1. Mua 2 don'
            WHEN order_count = 3 THEN '2.2. Mua 3 don'
            ELSE '2.3. Mua tu 4 don tro len'
        END AS frequency_tier
    FROM customer_behavior
),
drill_level_0 AS (
    SELECT
        'Cap 0: Toan bo khach hang (All Delivered)' AS drill_stage,
        '(ALL DELIVERED CUSTOMERS)'                  AS customer_granularity,
        count(customer_unique_id)                   AS customers,
        sum(order_count)                            AS delivered_orders,
        round(sum(total_spend), 2)                  AS delivered_payment_value,
        round(sum(total_spend) / nullif(sum(order_count), 0), 2) AS delivered_aov,
        round(avg(total_spend), 2)                  AS avg_monetary_per_customer
    FROM labeled_customers
),
drill_level_1 AS (
    SELECT
        'Cap 1: Khoan sau xuong Nhom hanh vi'       AS drill_stage,
        buyer_group                                 AS customer_granularity,
        count(customer_unique_id)                   AS customers,
        sum(order_count)                            AS delivered_orders,
        round(sum(total_spend), 2)                  AS delivered_payment_value,
        round(sum(total_spend) / nullif(sum(order_count), 0), 2) AS delivered_aov,
        round(avg(total_spend), 2)                  AS avg_monetary_per_customer
    FROM labeled_customers
    GROUP BY buyer_group
),
drill_level_2 AS (
    SELECT
        'Cap 2: Khoan sau xuong Bac tan suat chi tiet' AS drill_stage,
        '   -> ' || frequency_tier                  AS customer_granularity,
        count(customer_unique_id)                   AS customers,
        sum(order_count)                            AS delivered_orders,
        round(sum(total_spend), 2)                  AS delivered_payment_value,
        round(sum(total_spend) / nullif(sum(order_count), 0), 2) AS delivered_aov,
        round(avg(total_spend), 2)                  AS avg_monetary_per_customer
    FROM labeled_customers
    GROUP BY frequency_tier
)
SELECT * FROM drill_level_0
UNION ALL
SELECT * FROM drill_level_1
UNION ALL
SELECT * FROM drill_level_2;


-- =============================================================================
-- 6b) DRILL-DOWN (Chiều Địa lý): Đi từ Khái quát -> Chi tiết dọc theo Geography Hierarchy
--     Tuân thủ lý thuyết Concept Hierarchy Chiều Địa lý (Chapter 2 Slide 15, Chapter 3 Slide 25):
--     Toàn quốc (All 27 Bang) -> Khoan sâu vào Bang lớn nhất (Bang SP chiếm 42% doanh số) -> Khoan sâu vào các Thành phố (City) của Bang SP
--     Mô tả hành trình phân tích địa lý của nhà quản trị:
--       - Bước 1 (Cấp 0): Tổng thể toàn quốc (27 bang)
--       - Bước 2 (Cấp 1): Khoan sâu vào Bang SP (Sao Paulo)
--       - Bước 3 (Cấp 2): Khoan sâu vào Top 15 thành phố trong Bang SP có giá trị thanh toán cao nhất
-- =============================================================================
WITH geo_level_0 AS (
    SELECT
        'Cap 0: Toan quoc'                       AS drill_stage,
        '(ALL 27 STATES)'                        AS location_name,
        count(order_id)                          AS delivered_orders,
        count(DISTINCT customer_unique_id)       AS delivered_customers,
        round(sum(payment_value), 2)             AS delivered_payment_value,
        round(avg(raw_payment_value), 2)         AS delivered_aov
    FROM valid_customer_orders
),
geo_level_1 AS (
    SELECT
        'Cap 1: Khoan sau Bang SP (Sao Paulo)'   AS drill_stage,
        'Bang: ' || customer_state               AS location_name,
        count(order_id)                          AS delivered_orders,
        count(DISTINCT customer_unique_id)       AS delivered_customers,
        round(sum(payment_value), 2)             AS delivered_payment_value,
        round(avg(raw_payment_value), 2)         AS delivered_aov
    FROM valid_customer_orders
    WHERE customer_state = 'SP'
    GROUP BY customer_state
),
geo_level_2 AS (
    SELECT
        'Cap 2: Top thanh pho tai Bang SP'       AS drill_stage,
        '   -> ' || customer_city                AS location_name,
        count(order_id)                          AS delivered_orders,
        count(DISTINCT customer_unique_id)       AS delivered_customers,
        round(sum(payment_value), 2)             AS delivered_payment_value,
        round(avg(raw_payment_value), 2)         AS delivered_aov
    FROM valid_customer_orders
    WHERE customer_state = 'SP'
    GROUP BY customer_city
    ORDER BY sum(payment_value) DESC, count(order_id) DESC, customer_city ASC
    LIMIT 15
)
SELECT * FROM geo_level_0
UNION ALL
SELECT * FROM geo_level_1
UNION ALL
SELECT * FROM geo_level_2;


-- =============================================================================
-- 7a) SLICE: Cắt lát trên chiều Phân hạng Chi tiêu khách hàng (`spending_tier = 'VIP (> 1,000 R$)'`)
--     Theo lý thuyết Chapter 2-cont Slide 11 (Discretization) & Chapter 3 Slide 26 (Slice):
--     Rời rạc hóa tổng chi tiêu thành chiều khái niệm `spending_tier`, sau đó cố định 1 chiều
--     WHERE spending_tier = 'VIP (> 1,000 R$)' (Tổng 1,149 khách VIP — Hiển thị Top 20)
-- =============================================================================
WITH customer_spending_cube AS (
    SELECT
        customer_unique_id,
        max(customer_state)                    AS customer_state,
        max(customer_city)                     AS customer_city,
        count(order_id)                        AS delivered_orders,
        min(purchase_date)                     AS first_purchase_date,
        max(purchase_date)                     AS last_purchase_date,
        sum(payment_value)                     AS monetary_value,
        avg(raw_payment_value)                 AS delivered_aov,
        CASE
            WHEN sum(payment_value) > 1000 THEN 'VIP (> 1,000 R$)'
            WHEN sum(payment_value) >= 500 THEN 'High (500 - 1,000 R$)'
            WHEN sum(payment_value) >= 100 THEN 'Medium (100 - 500 R$)'
            ELSE 'Standard (< 100 R$)'
        END                                    AS spending_tier
    FROM valid_customer_orders
    GROUP BY customer_unique_id
)
SELECT
    customer_unique_id,
    spending_tier,
    customer_state,
    customer_city,
    delivered_orders,
    first_purchase_date,
    last_purchase_date,
    round(monetary_value, 2)                   AS vip_monetary_value,
    round(delivered_aov, 2)                    AS vip_delivered_aov
FROM customer_spending_cube
WHERE spending_tier = 'VIP (> 1,000 R$)'
ORDER BY monetary_value DESC, delivered_orders DESC, customer_unique_id ASC
LIMIT 20;


-- =============================================================================
-- 7b) SLICE (Tổng hợp theo Bang): Cố định lát cắt `spending_tier = 'VIP (> 1,000 R$)'`
--     và phân tích quy mô theo chiều Địa lý (`customer_state`)
-- =============================================================================
WITH customer_spending_cube AS (
    SELECT
        customer_unique_id,
        max(customer_state)          AS customer_state,
        count(order_id)              AS delivered_orders,
        sum(payment_value)           AS vip_spend,
        CASE
            WHEN sum(payment_value) > 1000 THEN 'VIP (> 1,000 R$)'
            WHEN sum(payment_value) >= 500 THEN 'High (500 - 1,000 R$)'
            WHEN sum(payment_value) >= 100 THEN 'Medium (100 - 500 R$)'
            ELSE 'Standard (< 100 R$)'
        END                          AS spending_tier
    FROM valid_customer_orders
    GROUP BY customer_unique_id
)
SELECT
    customer_state,
    spending_tier,
    count(customer_unique_id)                                                AS vip_customers,
    sum(delivered_orders)                                                    AS vip_delivered_orders,
    round(sum(vip_spend), 2)                                                 AS vip_monetary_value,
    round(avg(vip_spend), 2)                                                 AS avg_monetary_per_vip,
    round(sum(vip_spend) / nullif(sum(delivered_orders), 0), 2)              AS vip_delivered_aov,
    round(100.0 * sum(vip_spend) / sum(sum(vip_spend)) OVER (), 2)           AS pct_of_total_vip_spend
FROM customer_spending_cube
WHERE spending_tier = 'VIP (> 1,000 R$)'
GROUP BY customer_state, spending_tier
ORDER BY sum(vip_spend) DESC, count(customer_unique_id) DESC, customer_state ASC;


-- =============================================================================
-- 8a) DICE (Trích xuất Sub-cube đa chiều: Địa lý × Thời gian × Nhóm khách mua lặp lại):
--     Theo lý thuyết Chapter 2 Slide 23 & Chapter 3 Slide 26, 38:
--     Lọc đồng thời trên nhiều chiều:
--       (1) Chiều Địa lý: customer_state IN ('SP', 'RJ', 'MG')
--       (2) Chiều Thời gian: year BETWEEN 2017 AND 2018
--       (3) Chiều Phân loại khách: Repeat Buyer (tổng số đơn delivered >= 2)
--     Giữ nguyên các trục (customer_state, purchase_year) để hiển thị trọn vẹn các cell của Sub-cube!
-- =============================================================================
WITH repeat_buyer_dim AS (
    SELECT
        customer_unique_id,
        'Repeat Buyer (>= 2 don)' AS buyer_type
    FROM valid_customer_orders
    GROUP BY customer_unique_id
    HAVING count(order_id) >= 2
)
SELECT
    v.customer_state,
    v.year                                                                   AS purchase_year,
    r.buyer_type,
    count(DISTINCT v.customer_unique_id)                                     AS repeat_customers_in_cell,
    count(v.order_id)                                                        AS delivered_orders_in_cell,
    round(sum(v.payment_value), 2)                                           AS delivered_payment_value,
    round(sum(v.payment_value) / nullif(count(DISTINCT v.customer_unique_id), 0), 2) AS avg_spend_per_customer,
    round(avg(v.raw_payment_value), 2)                                       AS cell_delivered_aov
FROM valid_customer_orders AS v
JOIN repeat_buyer_dim AS r
    ON r.customer_unique_id = v.customer_unique_id
WHERE v.customer_state IN ('SP', 'RJ', 'MG')
  AND v.year BETWEEN 2017 AND 2018
GROUP BY v.customer_state, v.year, r.buyer_type
ORDER BY v.customer_state ASC, v.year ASC;


-- =============================================================================
-- 8b) DICE (Chi tiết Top 20 khách hàng trong khối Sub-cube tại Bang SP ∩ Năm 2017–2018 ∩ >= 2 đơn):
-- =============================================================================
SELECT
    customer_unique_id,
    customer_state,
    max(customer_city)                         AS customer_city,
    count(order_id)                            AS delivered_orders,
    min(purchase_date)                         AS first_order_date,
    max(purchase_date)                         AS last_order_date,
    max(purchase_date) - min(purchase_date)    AS lifespan_days,
    round(sum(payment_value), 2)               AS delivered_payment_value,
    round(avg(raw_payment_value), 2)           AS delivered_aov
FROM valid_customer_orders
WHERE customer_state = 'SP'
  AND year BETWEEN 2017 AND 2018
GROUP BY customer_unique_id, customer_state
HAVING count(order_id) >= 2
ORDER BY count(order_id) DESC, sum(payment_value) DESC, customer_unique_id ASC
LIMIT 20;


-- =============================================================================
-- 9a) PIVOT: Ma trận 27 Bang (dòng) × 8 Trạng thái đơn (cột) + Giá trị thanh toán delivered
--     Xoay trục (Rotate) chiều `order_status` thành các cột để so sánh vận hành giữa 27 Bang
-- =============================================================================
SELECT
    coalesce(f.customer_state, 'UNKNOWN')                                    AS customer_state,
    count(f.order_id) FILTER (WHERE f.order_status = 'delivered')            AS delivered,
    count(f.order_id) FILTER (WHERE f.order_status = 'shipped')              AS shipped,
    count(f.order_id) FILTER (WHERE f.order_status = 'canceled')             AS canceled,
    count(f.order_id) FILTER (WHERE f.order_status = 'unavailable')          AS unavailable,
    count(f.order_id) FILTER (WHERE f.order_status = 'invoiced')             AS invoiced,
    count(f.order_id) FILTER (WHERE f.order_status = 'processing')           AS processing,
    count(f.order_id) FILTER (WHERE f.order_status = 'created')              AS created,
    count(f.order_id) FILTER (WHERE f.order_status = 'approved')             AS approved,
    count(f.order_id)                                                        AS total_orders,
    round(
        100.0 * count(f.order_id) FILTER (WHERE f.order_status = 'delivered')
        / nullif(count(f.order_id), 0),
        2
    )                                                                        AS delivered_rate_pct,
    round(
        coalesce(sum(f.total_payment_value) FILTER (WHERE f.order_status = 'delivered'), 0),
        2
    )                                                                        AS delivered_payment_value
FROM dw.fact_customer_order AS f
GROUP BY f.customer_state
ORDER BY delivered_payment_value DESC, total_orders DESC, f.customer_state ASC;


-- =============================================================================
-- 9b) PIVOT: Ma trận 5 Bang cố định (SP, RJ, MG, RS, PR) × 3 Năm (2016..2018)
--     và Phân phối Quy mô đơn hàng đã rời rạc hóa (Discretized Order Size Tiers: <100, 100-500, >500 R$)
--     Đồng bộ 5 bang cố định với Pivot của Bạn 2, chỉ tính trên đơn delivered
-- =============================================================================
SELECT
    customer_state,
    round(coalesce(sum(payment_value) FILTER (WHERE year = 2016), 0), 2)     AS pay_2016,
    round(coalesce(sum(payment_value) FILTER (WHERE year = 2017), 0), 2)     AS pay_2017,
    round(coalesce(sum(payment_value) FILTER (WHERE year = 2018), 0), 2)     AS pay_2018,
    round(sum(payment_value), 2)                                             AS five_state_payment_total,
    count(order_id) FILTER (WHERE year = 2016)                               AS orders_2016,
    count(order_id) FILTER (WHERE year = 2017)                               AS orders_2017,
    count(order_id) FILTER (WHERE year = 2018)                               AS orders_2018,
    count(order_id) FILTER (WHERE payment_value < 100)                       AS small_orders_under_100,
    count(order_id) FILTER (WHERE payment_value BETWEEN 100 AND 500)         AS medium_orders_100_to_500,
    count(order_id) FILTER (WHERE payment_value > 500)                       AS large_orders_over_500
FROM valid_customer_orders
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
GROUP BY customer_state
ORDER BY sum(payment_value) DESC, customer_state ASC;


-- =============================================================================
-- 10) TRUY VẤN NÂNG CAO (Window Functions):
--     Xếp hạng Top 3 khách hàng chi tiêu lớn nhất trong từng Bang lớn (Top Spenders by State)
--     và Phân vị tích lũy chi tiêu toàn quốc (Percentile Profiling)
--     Cơ sở lý thuyết:
--       - Window Functions trong ROLAP: `DENSE_RANK() OVER (PARTITION BY ...)` và `PERCENT_RANK()`
--       - Đồng bộ cấu trúc với Bạn 1 (`LAG` MoM Growth) và Bạn 2 (`DENSE_RANK` Top 3 danh mục theo bang)
--       - Toàn bộ mô hình phân khúc RFM, K-Means Clustering, kịch bản What-if và khuyến nghị
--         chiến lược được chuyển trọn vẹn sang Giai đoạn 5 (DSS) theo đúng phân công môn học.
-- =============================================================================
WITH customer_spend AS (
    SELECT
        customer_unique_id,
        customer_state,
        max(customer_city)                             AS customer_city,
        count(order_id)                                AS delivered_orders,
        round(sum(payment_value), 2)                   AS total_spend,
        round(avg(raw_payment_value), 2)               AS customer_aov
    FROM valid_customer_orders
    GROUP BY customer_unique_id, customer_state
),
ranked_customers AS (
    SELECT
        customer_unique_id,
        customer_state,
        customer_city,
        delivered_orders,
        total_spend,
        customer_aov,
        dense_rank() OVER (
            PARTITION BY customer_state
            ORDER BY total_spend DESC, delivered_orders DESC, customer_unique_id ASC
        )                                              AS state_spend_rank,
        round(
            (percent_rank() OVER (ORDER BY total_spend ASC, customer_unique_id ASC) * 100)::numeric,
            2
        )                                              AS national_spend_percentile
    FROM customer_spend
)
SELECT
    customer_state,
    state_spend_rank,
    customer_unique_id,
    customer_city,
    delivered_orders,
    total_spend,
    customer_aov,
    national_spend_percentile || '%'                   AS spend_percentile_tier
FROM ranked_customers
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
  AND state_spend_rank <= 3
ORDER BY customer_state ASC, state_spend_rank ASC, customer_unique_id ASC;
