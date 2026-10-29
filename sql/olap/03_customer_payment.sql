-- =============================================================================
-- FILE: sql/olap/03_customer_payment.sql
-- CHỦ ĐỀ: Bạn 3 — Customer & Payment (Hành vi khách hàng, Thanh toán & RFM)
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
--   1. Đơn tính doanh thu / chi tiêu (Monetary) / AOV / Repeat Rate / RFM:
--      CHỈ lấy đơn có `order_status = 'delivered'` (96,478 đơn của 93,358 khách hàng).
--   2. Phân biệt chỉ số tiền giữa 2 Fact:
--      - Bạn 1 & Bạn 2 đọc `dw.fact_sales`: tính Doanh thu hàng hóa = `SUM(price)` (13,221,498.11 R$)
--        và Cước vận chuyển = `SUM(freight_value)` (2,198,266.93 R$).
--      - Bạn 3 đọc `dw.fact_customer_order`: tính Giá trị thanh toán đơn hàng đã giao
--        (`delivered_payment_value` / `Monetary`) = `SUM(total_payment_value)` (15,422,461.77 R$,
--        đã gồm tiền hàng + cước vận chuyển) và `AOV` = `AVG(total_payment_value)` (159.86 R$).
--   3. Mốc thời gian: gắn theo `purchase_date_key` (ngày khách đặt hàng).
--   4. Phá hòa (Tie-breaking): mọi câu xếp hạng và Window Function (`NTILE`, `ROW_NUMBER`,
--      `DENSE_RANK`) đều có khóa phụ đến tận `customer_unique_id` hoặc `customer_state`
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
-- 4a) ROLL-UP (Đơn delivered): Năm -> Bang -> Toàn bộ
--     grouping_state / grouping_year = 1 là dòng tổng của cấp đó;
--     grouping_level: 0 = chi tiết (bang, năm), 1 = tổng bang, 3 = grand total
-- =============================================================================
SELECT
    CASE
        WHEN grouping(customer_state) = 1 THEN '(ALL STATES)'
        ELSE coalesce(customer_state, '(NULL STATE)')
    END                                        AS customer_state,
    CASE
        WHEN grouping(year) = 1 THEN '(ALL YEARS)'
        ELSE year::text
    END                                        AS purchase_year,
    grouping(customer_state)                   AS grouping_state,
    grouping(year)                             AS grouping_year,
    grouping(customer_state, year)             AS grouping_level,
    count(order_id)                            AS delivered_orders,
    count(DISTINCT customer_unique_id)         AS delivered_customers,
    round(sum(payment_value), 2)               AS delivered_payment_value,
    round(avg(raw_payment_value), 2)           AS delivered_aov
FROM valid_customer_orders
GROUP BY ROLLUP (customer_state, year)
ORDER BY
    grouping(customer_state) ASC,
    customer_state ASC,
    grouping(year) ASC,
    year ASC;


-- =============================================================================
-- 4b) ROLL-UP (Vận hành trạng thái đơn): Bang -> Trạng thái đơn -> Toàn bộ
--     Cột `delivered_payment_value` chỉ cộng tiền của đơn `order_status = 'delivered'`
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
-- 6a) DRILL-DOWN (Cấp 0 -> Cấp 1 -> Cấp 2):
--     Tổng khách hàng delivered -> Nhóm mua 1 lần vs Mua nhiều lần -> Bậc tần suất (1, 2, 3, >=4 đơn)
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
    coalesce(buyer_group, '(ALL DELIVERED CUSTOMERS)')                       AS buyer_group,
    coalesce(frequency_tier, '(GROUP SUBTOTAL)')                             AS frequency_tier,
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
    grouping(buyer_group) DESC,
    buyer_group ASC,
    grouping(frequency_tier) DESC,
    frequency_tier ASC;


-- =============================================================================
-- 6b) DRILL-DOWN (Cấp 2 -> Cấp 3):
--     Đi sâu vào nhóm Khách hàng mua nhiều lần (Repeat Buyers) tại 5 bang lớn theo từng năm
-- =============================================================================
WITH repeat_customers AS (
    SELECT customer_unique_id
    FROM valid_customer_orders
    GROUP BY customer_unique_id
    HAVING count(order_id) >= 2
)
SELECT
    v.year                                     AS purchase_year,
    v.customer_state,
    count(DISTINCT v.customer_unique_id)       AS active_repeat_customers,
    count(v.order_id)                          AS delivered_orders,
    round(sum(v.payment_value), 2)             AS delivered_payment_value,
    round(avg(v.raw_payment_value), 2)         AS delivered_aov
FROM valid_customer_orders AS v
JOIN repeat_customers AS r
    ON r.customer_unique_id = v.customer_unique_id
WHERE v.customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
GROUP BY v.year, v.customer_state
ORDER BY v.year ASC, sum(v.payment_value) DESC, v.customer_state ASC;


-- =============================================================================
-- 7a) SLICE: Tập khách hàng VIP có tổng chi tiêu > 1,000 R$ trên đơn delivered
--     (Tổng 1,149 khách VIP toàn kho — Hiển thị Top 20 khách VIP đứng đầu)
-- =============================================================================
SELECT
    customer_unique_id,
    max(customer_state)                        AS customer_state,
    max(customer_city)                         AS customer_city,
    count(order_id)                            AS delivered_orders,
    min(purchase_date)                         AS first_purchase_date,
    max(purchase_date)                         AS last_purchase_date,
    round(sum(payment_value), 2)               AS vip_monetary_value,
    round(avg(raw_payment_value), 2)           AS vip_delivered_aov
FROM valid_customer_orders
GROUP BY customer_unique_id
HAVING sum(payment_value) > 1000
ORDER BY sum(payment_value) DESC, count(order_id) DESC, customer_unique_id ASC
LIMIT 20;


-- =============================================================================
-- 7b) SLICE (Tổng hợp theo Bang): Quy mô tập khách hàng VIP (> 1,000 R$) tại từng Bang
-- =============================================================================
WITH vip_customers AS (
    SELECT
        customer_unique_id,
        max(customer_state)          AS customer_state,
        count(order_id)              AS delivered_orders,
        sum(payment_value)           AS vip_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
    HAVING sum(payment_value) > 1000
)
SELECT
    customer_state,
    count(customer_unique_id)                                                AS vip_customers,
    sum(delivered_orders)                                                    AS vip_delivered_orders,
    round(sum(vip_spend), 2)                                                 AS vip_monetary_value,
    round(avg(vip_spend), 2)                                                 AS avg_monetary_per_vip,
    round(sum(vip_spend) / nullif(sum(delivered_orders), 0), 2)              AS vip_delivered_aov,
    round(100.0 * sum(vip_spend) / sum(sum(vip_spend)) OVER (), 2)           AS pct_of_total_vip_spend
FROM vip_customers
GROUP BY customer_state
ORDER BY sum(vip_spend) DESC, count(customer_unique_id) DESC, customer_state ASC;


-- =============================================================================
-- 8a) DICE (Tổng hợp theo Bang):
--     Đơn delivered ∩ 3 Bang lớn (SP, RJ, MG) ∩ Năm 2017–2018 ∩ Khách mua từ 2 đơn trở lên
-- =============================================================================
WITH dice_customers AS (
    SELECT
        customer_unique_id,
        customer_state,
        count(order_id)              AS orders_in_dice,
        sum(payment_value)           AS spend_in_dice
    FROM valid_customer_orders
    WHERE customer_state IN ('SP', 'RJ', 'MG')
      AND year BETWEEN 2017 AND 2018
    GROUP BY customer_unique_id, customer_state
    HAVING count(order_id) >= 2
)
SELECT
    customer_state,
    count(customer_unique_id)                                                AS repeat_customers_in_dice,
    sum(orders_in_dice)                                                      AS delivered_orders_in_dice,
    round(sum(spend_in_dice), 2)                                             AS delivered_payment_value,
    round(avg(spend_in_dice), 2)                                             AS avg_spend_per_customer,
    round(sum(spend_in_dice) / nullif(sum(orders_in_dice), 0), 2)            AS dice_delivered_aov
FROM dice_customers
GROUP BY customer_state
ORDER BY sum(spend_in_dice) DESC, customer_state ASC;


-- =============================================================================
-- 8b) DICE (Chi tiết Top 20 khách hàng):
--     Khách hàng ở bang 'SP' ∩ Đơn delivered ∩ Năm 2017–2018 ∩ Số đơn >= 2 (1,210 khách)
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
-- 9b) PIVOT: Ma trận 5 Bang cố định (SP, RJ, MG, RS, PR) × 3 Năm (2016..2018) & Quy mô đơn
--     Đồng bộ 5 bang cố định với Pivot của Bạn 2, chỉ tính trên đơn delivered
-- =============================================================================
SELECT
    customer_state,
    round(coalesce(sum(payment_value) FILTER (WHERE year = 2016), 0), 2)     AS pay_2016,
    round(coalesce(sum(payment_value) FILTER (WHERE year = 2017), 0), 2)     AS pay_2017,
    round(coalesce(sum(payment_value) FILTER (WHERE year = 2018), 0), 2)     AS pay_2018,
    round(sum(payment_value), 2)                                             AS five_state_payment_total,
    count(order_id) FILTER (WHERE payment_value < 100)                       AS small_orders_under_100,
    count(order_id) FILTER (WHERE payment_value BETWEEN 100 AND 500)         AS medium_orders_100_to_500,
    count(order_id) FILTER (WHERE payment_value > 500)                       AS large_orders_over_500
FROM valid_customer_orders
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
GROUP BY customer_state
ORDER BY sum(payment_value) DESC, customer_state ASC;


-- =============================================================================
-- 10) TRUY VẤN NÂNG CAO (Window Functions):
--     Chấm điểm RFM (`NTILE(4)` + `CASE WHEN`) và xếp hạng Top 20 khách hàng dẫn đầu
--     Tie-breaker cuối cùng luôn là `customer_unique_id ASC` để cố định kết quả 100%
-- =============================================================================
WITH snapshot_anchor AS (
    SELECT max(purchase_date) AS analysis_date
    FROM valid_customer_orders
),
rfm_raw AS (
    SELECT
        customer_unique_id,
        max(customer_state)                                                  AS customer_state,
        (SELECT analysis_date FROM snapshot_anchor) - max(purchase_date)     AS recency_days,
        count(order_id)                                                      AS frequency,
        round(sum(payment_value), 2)                                         AS monetary
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
rfm_scored AS (
    SELECT
        customer_unique_id,
        customer_state,
        recency_days,
        frequency,
        monetary,
        -- R Score: recency_days càng nhỏ (mới mua gần đây) -> điểm càng cao (4)
        ntile(4) OVER (
            ORDER BY recency_days DESC, monetary ASC, customer_unique_id ASC
        )                                                                    AS r_score,
        -- F Score: dùng CASE WHEN theo ngưỡng số đơn thực tế (vì 97% khách chỉ có 1 đơn)
        CASE
            WHEN frequency >= 4 THEN 4
            WHEN frequency = 3  THEN 3
            WHEN frequency = 2  THEN 2
            ELSE 1
        END                                                                  AS f_score,
        -- M Score: monetary càng lớn -> điểm càng cao (4)
        ntile(4) OVER (
            ORDER BY monetary ASC, recency_days DESC, customer_unique_id ASC
        )                                                                    AS m_score,
        row_number() OVER (
            ORDER BY monetary DESC, frequency DESC, recency_days ASC, customer_unique_id ASC
        )                                                                    AS national_rank
    FROM rfm_raw
),
rfm_segmented AS (
    SELECT
        *,
        (r_score::text || f_score::text || m_score::text)                    AS rfm_cell,
        (r_score + f_score + m_score)                                        AS rfm_total_score,
        CASE
            WHEN f_score >= 2 AND r_score >= 3 AND m_score >= 3
                THEN '1. Champions / VIP'
            WHEN f_score >= 2 AND (r_score >= 2 OR m_score >= 3)
                THEN '2. Loyal Customers'
            WHEN f_score = 1 AND r_score >= 3 AND m_score = 4
                THEN '3. Potential VIP / Big Spenders'
            WHEN f_score = 1 AND r_score >= 3 AND m_score <= 3
                THEN '4. New & Promising Customers'
            WHEN r_score <= 2 AND (f_score >= 2 OR m_score >= 3)
                THEN '5. At Risk'
            ELSE '6. Hibernating / Lost'
        END                                                                  AS customer_segment
    FROM rfm_scored
)
SELECT
    customer_unique_id,
    customer_state,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    rfm_cell,
    rfm_total_score,
    customer_segment,
    national_rank
FROM rfm_segmented
ORDER BY rfm_total_score DESC, monetary DESC, frequency DESC, recency_days ASC, customer_unique_id ASC
LIMIT 20;


-- =============================================================================
-- 11) BÁO CÁO TỔNG HỢP 6 PHÂN KHÚC RFM & KHUYẾN NGHỊ CHIẾN LƯỢC DSS
--     Tổng số khách = 93,358 | Tổng số đơn = 96,478 | Tổng Monetary = 15,422,461.77 R$
-- =============================================================================
WITH snapshot_anchor AS (
    SELECT max(purchase_date) AS analysis_date
    FROM valid_customer_orders
),
rfm_raw AS (
    SELECT
        customer_unique_id,
        (SELECT analysis_date FROM snapshot_anchor) - max(purchase_date)     AS recency_days,
        count(order_id)                                                      AS frequency,
        round(sum(payment_value), 2)                                         AS monetary
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
rfm_scored AS (
    SELECT
        customer_unique_id,
        recency_days,
        frequency,
        monetary,
        ntile(4) OVER (
            ORDER BY recency_days DESC, monetary ASC, customer_unique_id ASC
        )                                                                    AS r_score,
        CASE
            WHEN frequency >= 4 THEN 4
            WHEN frequency = 3  THEN 3
            WHEN frequency = 2  THEN 2
            ELSE 1
        END                                                                  AS f_score,
        ntile(4) OVER (
            ORDER BY monetary ASC, recency_days DESC, customer_unique_id ASC
        )                                                                    AS m_score
    FROM rfm_raw
),
rfm_segmented AS (
    SELECT
        *,
        CASE
            WHEN f_score >= 2 AND r_score >= 3 AND m_score >= 3
                THEN '1. Champions / VIP'
            WHEN f_score >= 2 AND (r_score >= 2 OR m_score >= 3)
                THEN '2. Loyal Customers'
            WHEN f_score = 1 AND r_score >= 3 AND m_score = 4
                THEN '3. Potential VIP / Big Spenders'
            WHEN f_score = 1 AND r_score >= 3 AND m_score <= 3
                THEN '4. New & Promising Customers'
            WHEN r_score <= 2 AND (f_score >= 2 OR m_score >= 3)
                THEN '5. At Risk'
            ELSE '6. Hibernating / Lost'
        END                                                                  AS customer_segment
    FROM rfm_scored
)
SELECT
    customer_segment,
    count(customer_unique_id)                                                AS customers,
    round(100.0 * count(customer_unique_id) / sum(count(customer_unique_id)) OVER (), 2) AS pct_customers,
    sum(frequency)                                                           AS delivered_orders,
    round(avg(recency_days), 1)                                              AS avg_recency_days,
    round(avg(frequency), 2)                                                 AS avg_frequency,
    round(avg(monetary), 2)                                                  AS avg_monetary,
    round(sum(monetary), 2)                                                  AS total_monetary_value,
    round(100.0 * sum(monetary) / sum(sum(monetary)) OVER (), 2)             AS pct_monetary_share,
    CASE customer_segment
        WHEN '1. Champions / VIP'
            THEN 'Loyalty Reward, uu dai doc quyen, cham soc VIP & gioi thieu san pham cao cap'
        WHEN '2. Loyal Customers'
            THEN 'Cross-sell / Up-sell theo danh muc yeu thich, tich diem thuong duy tri tan suat mua'
        WHEN '3. Potential VIP / Big Spenders'
            THEN 'Tang voucher mua lan 2, goi y san pham bo tro de chuyen doi thanh Champions'
        WHEN '4. New & Promising Customers'
            THEN 'Kich hoat chien dich Welcome & khuyen mai don hang thu 2 trong 30 ngay'
        WHEN '5. At Risk'
            THEN 'Chien dich Win-back / Re-engagement khan cap voi uu dai ca nhan hoa'
        ELSE 'Chien dich Remarketing chi phi thap (Email/Push tu dong), khong uu tien ngan sach lon'
    END                                                                      AS recommended_action
FROM rfm_segmented
GROUP BY customer_segment
ORDER BY customer_segment ASC;
