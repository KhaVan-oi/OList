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
--      - Bạn 1 & Bạn 2 đọc `dw.fact_sales`: tính Tổng giá trị hàng hóa = `SUM(price)` (13,221,498.11 R$),
--        Cước vận chuyển = `SUM(freight_value)` (2,198,275.64 R$), tổng tiền hàng + cước = 15,419,773.75 R$.
--      - Bạn 3 đọc `dw.fact_customer_order`: tính Tổng giá trị thanh toán ghi nhận ở cấp đơn hàng
--        (`delivered_payment_value` / `Monetary`) = `SUM(total_payment_value)` (15,422,461.77 R$)
--        và `AOV` = `AVG(total_payment_value)` (159.86 R$ tính trên 96,477 đơn có thanh toán hợp lệ).
--        (Chênh lệch toàn kho giữa 2 Fact: 15,422,461.77 - 15,419,773.75 = 2,688.02 R$).
--   3. Mốc thời gian: gắn theo `purchase_date_key` (ngày khách đặt hàng).
--   4. Phá hòa (Tie-breaking):
--      - Các truy vấn dùng ROW_NUMBER() và ORDER BY ... LIMIT đều có khóa phụ đủ để xác định thứ tự ổn định,
--        ví dụ: customer_unique_id, order_id, customer_state, customer_city hoặc year tùy từng truy vấn.
--      - DENSE_RANK() và PERCENT_RANK() chỉ sắp xếp theo giá trị đo để bảo toàn trọn vẹn ngữ nghĩa đồng hạng (ties).
-- =============================================================================

DROP VIEW IF EXISTS pg_temp.valid_customer_orders;

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
--    Tổng khách hàng delivered / tổng số đơn delivered / đơn có tiền / đơn thiếu tiền / Monetary / AOV
--    Quy ước ngữ nghĩa & chuẩn hóa tài chính:
--      - COALESCE(total_payment_value, 0) chỉ là quy ước kỹ thuật xử lý dữ liệu thiếu khi cộng dồn.
--      - COUNT(raw_payment_value) chỉ đếm các đơn có payment hợp lệ.
--      - AVG(raw_payment_value) tự động bỏ qua NULL theo chuẩn SQL.
--      - Đơn có total_payment_value IS NULL trong dw.fact_customer_order tại thời điểm phân tích (không suy diễn nguyên nhân NULL).
--      - AOV = SUM(raw_payment_value) / COUNT(raw_payment_value)
--        (chỉ tính trên các đơn delivered có total_payment_value hợp lệ: 96,477 đơn).
-- =============================================================================
SELECT
    count(DISTINCT customer_unique_id)                                       AS delivered_customers,
    count(order_id)                                                          AS delivered_orders,
    count(raw_payment_value)                                                 AS orders_with_payment,
    count(order_id) FILTER (WHERE raw_payment_value IS NULL)                 AS missing_payment_orders,
    round(sum(payment_value), 2)                                             AS delivered_payment_value,
    round(avg(raw_payment_value), 2)                                         AS delivered_aov
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
-- 2) KPI Cơ cấu số lượng và tỷ trọng đơn hàng theo 8 trạng thái order_status,
--    kèm giá trị thanh toán và AOV của đơn delivered
--    Đọc toàn bộ dw.fact_customer_order JOIN dw.dim_customer để đếm `customer_unique_id`
--    nhất quán 100% với KPI 0, 1, 3; cột `delivered_payment_value` và `delivered_aov`
--    CHỈ ghi nhận cho trạng thái 'delivered'.
--    Lưu ý: `unique_customers` được đếm DISTINCT riêng trong từng trạng thái (Non-additive Measure:
--    không cộng dồn giữa các trạng thái để suy ra khách duy nhất toàn kho — 203 khách đa trạng thái tạo ra tổng cộng dọc
--    8 trạng thái = 96,300 lượt khách-trạng thái trên 96,096 khách duy nhất toàn hệ thống).
--    Cột `avg_approval_delay_days` tính độ trễ phê duyệt trung bình trên các đơn có `approved_date_key` hợp lệ
--    và tra cứu được trong `dw.dim_date` (kết quả thực tế: đơn delivered có độ trễ duyệt trung bình = 0,51 ngày).
-- =============================================================================
SELECT
    f.order_status,
    count(f.order_id)                                                        AS orders,
    count(DISTINCT c.customer_unique_id)                                     AS unique_customers,
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
JOIN dw.dim_customer AS c
    ON c.customer_key = f.customer_key
JOIN dw.dim_date AS dp
    ON dp.date_key = f.purchase_date_key
LEFT JOIN dw.dim_date AS da
    ON da.date_key = f.approved_date_key
GROUP BY f.order_status
ORDER BY count(f.order_id) DESC, f.order_status ASC;


-- =============================================================================
-- 3) KPI Số khách hàng, số đơn, tổng giá trị thanh toán và AOV theo Bang
--    Chỉ tính trên đơn delivered (`valid_customer_orders`).
--    Lưu ý ngữ nghĩa địa lý: `customer_state` là bang giao hàng của từng đơn delivered (khách hàng có đơn giao đến bang).
--    Một khách hàng phát sinh đơn ở nhiều bang sẽ được đếm tại từng bang tương ứng
--    (`delivered_customers` là độ đo phi cộng gộp — Non-additive Measure qua chiều địa lý:
--    có 37 khách mua xuyên bang — gồm 36 khách ở 2 bang và 1 khách ở 3 bang — tạo ra 38 lượt dư,
--    nên tổng cộng dọc 27 bang = 93,396 lượt khách-bang so với 93,358 khách duy nhất toàn quốc).
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
--     Cung cấp 3 cấp grouping tương ứng bitmask grouping_level:
--       + grouping_level = 0: 4 dòng chi tiết bậc tần suất (buyer_group, frequency_tier)
--       + grouping_level = 1: 2 dòng Subtotal theo nhóm hành vi (buyer_group, ALL)
--       + grouping_level = 3: 1 dòng Grand Total toàn bộ khách hàng delivered (ALL, ALL)
-- =============================================================================
WITH customer_behavior AS (
    SELECT
        customer_unique_id,
        count(order_id)              AS order_count,
        count(raw_payment_value)     AS valid_payment_orders,
        sum(payment_value)           AS total_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
labeled_customers AS (
    SELECT
        customer_unique_id,
        order_count,
        valid_payment_orders,
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
    round(sum(total_spend) / nullif(sum(valid_payment_orders), 0), 2)         AS group_delivered_aov,
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
--     Cột `delivered_payment_value` và `delivered_aov` chỉ tính cho đơn `order_status = 'delivered'`
--     (dùng FILTER (WHERE f.order_status = 'delivered')).
--     grouping_level: 0 = chi tiết (order_status, customer_state), 1 = Subtotal theo order_status, 3 = Grand Total.
--     Ở các dòng Subtotal của trạng thái khác ('canceled', 'shipped'...), delivered_payment_value = 0,00 R$;
--     chỉ tại dòng Subtotal của 'delivered' và Grand Total toàn bộ (grouping_level = 3), delivered_payment_value
--     mới đạt đầy đủ 15.422.461,77 R$, trong khi total_orders ở Grand Total cộng dồn đủ 99.441 đơn hàng toàn kho.
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
-- 5) CUBE (Đơn delivered): Đa chiều 5 Bang lớn (SP, RJ, MG, RS, PR) × 3 Năm cố định (2016..2018)
--    Xác nhận kết quả thực thi thực tế trên database: CUBE trả về chính xác đúng 24 dòng kết quả, gồm:
--      + 15 ô chi tiết (Bang, Năm) (grouping_level = 0, đủ 5 bang × 3 năm đều phát sinh đơn).
--      + 5 dòng Subtotal theo Bang (grouping_level = 1).
--      + 3 dòng Subtotal theo Năm (grouping_level = 2).
--      + 1 dòng Grand Total toàn Cube (grouping_level = 3).
--    Lưu ý: Cột delivered_customers là độ đo phi cộng gộp (Non-additive Measure), không cộng dồn số khách giữa các ô để suy ra tổng khách toàn Cube.
-- =============================================================================
SELECT
    CASE
        WHEN grouping(customer_state) = 1 THEN '(ALL 5 STATES)'
        ELSE customer_state
    END                                        AS customer_state,
    CASE
        WHEN grouping(year) = 1 THEN '(ALL 3 YEARS)'
        ELSE year::text
    END                                        AS purchase_year,
    grouping(customer_state, year)             AS grouping_level,
    count(order_id)                            AS delivered_orders,
    count(DISTINCT customer_unique_id)         AS delivered_customers,
    round(sum(payment_value), 2)               AS delivered_payment_value,
    round(avg(raw_payment_value), 2)           AS delivered_aov
FROM valid_customer_orders
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
  AND year IN (2016, 2017, 2018)
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
--       - Bước 3 (Cấp 2): Khoan sâu mổ xẻ chi tiết từng bậc tần suất (Mua 1 đơn: 90.557 khách, Mua 2 đơn: 2.573 khách, Mua 3 đơn: 181 khách, >=4 đơn: 47 khách)
-- =============================================================================
WITH customer_behavior AS (
    SELECT
        customer_unique_id,
        count(order_id)              AS order_count,
        count(raw_payment_value)     AS valid_payment_orders,
        sum(payment_value)           AS total_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
labeled_customers AS (
    SELECT
        customer_unique_id,
        order_count,
        valid_payment_orders,
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
        round(sum(total_spend) / nullif(sum(valid_payment_orders), 0), 2) AS delivered_aov,
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
        round(sum(total_spend) / nullif(sum(valid_payment_orders), 0), 2) AS delivered_aov,
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
        round(sum(total_spend) / nullif(sum(valid_payment_orders), 0), 2) AS delivered_aov,
        round(avg(total_spend), 2)                  AS avg_monetary_per_customer
    FROM labeled_customers
    GROUP BY frequency_tier
)
SELECT
    drill_stage,
    customer_granularity,
    customers,
    delivered_orders,
    delivered_payment_value,
    delivered_aov,
    avg_monetary_per_customer
FROM (
    SELECT
        0 AS stage_order,
        0 AS row_order,
        *
    FROM drill_level_0

    UNION ALL

    SELECT
        1 AS stage_order,
        CASE
            WHEN customer_granularity LIKE '1.%' THEN 1
            ELSE 2
        END AS row_order,
        *
    FROM drill_level_1

    UNION ALL

    SELECT
        2 AS stage_order,
        CASE
            WHEN customer_granularity LIKE '%1 don%' THEN 1
            WHEN customer_granularity LIKE '%2 don%' THEN 2
            WHEN customer_granularity LIKE '%3 don%' THEN 3
            ELSE 4
        END AS row_order,
        *
    FROM drill_level_2
) AS combined_drill
ORDER BY stage_order ASC, row_order ASC;


-- =============================================================================
-- 6b) DRILL-DOWN (Chiều Địa lý): Đi từ Khái quát -> Chi tiết dọc theo Geography Hierarchy
--     Tuân thủ lý thuyết Concept Hierarchy Chiều Địa lý (Chapter 2 Slide 15, Chapter 3 Slide 25):
--     Toàn quốc (All 27 Bang) -> Khoan sâu vào Bang SP (chọn do có số đơn delivered lớn nhất toàn quốc:
--     40.501 đơn, chiếm 41,98%; tỷ trọng thanh toán 37,41% là chỉ số bổ sung) -> Khoan sâu vào Top 15 Thành phố của SP (chỉ gồm customer_city IS NOT NULL)
--     Mô tả hành trình phân tích địa lý của nhà quản trị:
--       - Bước 1 (Cấp 0): Tổng thể toàn quốc (27 bang)
--       - Bước 2 (Cấp 1): Khoan sâu vào Bang SP (Sao Paulo)
--       - Bước 3 (Cấp 2): Khoan sâu vào Top 15 thành phố trong Bang SP theo giá trị thanh toán delivered lớn nhất (customer_city IS NOT NULL, xếp theo delivered_payment_value DESC, không diễn giải là Top theo số đơn)
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
      AND customer_city IS NOT NULL
    GROUP BY customer_city
    ORDER BY sum(payment_value) DESC, count(order_id) DESC, customer_city ASC
    LIMIT 15
)
SELECT
    drill_stage,
    location_name,
    delivered_orders,
    delivered_customers,
    delivered_payment_value,
    delivered_aov
FROM (
    SELECT
        0 AS stage_order,
        0 AS row_order,
        *
    FROM geo_level_0

    UNION ALL

    SELECT
        1 AS stage_order,
        0 AS row_order,
        *
    FROM geo_level_1

    UNION ALL

    SELECT
        2 AS stage_order,
        row_number() OVER (ORDER BY delivered_payment_value DESC, delivered_orders DESC, location_name ASC) AS row_order,
        *
    FROM geo_level_2
) AS combined_geo
ORDER BY stage_order ASC, row_order ASC;


-- =============================================================================
-- 7a) SLICE: Cắt lát trên chiều Phân hạng Chi tiêu khách hàng (`spending_tier = 'VIP (>= 1,000 R$)'`)
--     Theo lý thuyết Chapter 2-cont Slide 11 (Discretization) & Chapter 3 Slide 26 (Slice):
--     Rời rạc hóa tổng chi tiêu toàn kho thành các khoảng nửa mở: Standard [0, 100), Medium [100, 500),
--     High [500, 1000), VIP [1000, +∞). Cố định lát cắt 1 chiều WHERE spending_tier = 'VIP (>= 1,000 R$)'
--     Địa chỉ khách hàng: Địa chỉ giao hàng tại đơn delivered có ngày đặt hàng gần nhất trên toàn bộ
--     lịch sử đơn delivered của khách hàng (dùng order_id ASC làm khóa phá hòa ổn định; không khẳng định đây chắc chắn là địa chỉ mới nhất theo thời gian thực).
-- =============================================================================
WITH customer_latest_address AS (
    SELECT customer_unique_id, customer_city AS latest_customer_city, customer_state AS latest_customer_state
    FROM (
        SELECT
            customer_unique_id,
            customer_city,
            customer_state,
            row_number() OVER (
                PARTITION BY customer_unique_id
                ORDER BY purchase_date DESC, order_id ASC
            ) AS rn
        FROM valid_customer_orders
    ) t
    WHERE rn = 1
),
customer_spending_cube AS (
    SELECT
        c.customer_unique_id,
        a.latest_customer_state,
        a.latest_customer_city,
        count(c.order_id)                      AS delivered_orders,
        count(c.raw_payment_value)             AS orders_with_payment,
        min(c.purchase_date)                   AS first_purchase_date,
        max(c.purchase_date)                   AS last_purchase_date,
        sum(c.payment_value)                   AS monetary_value,
        round(avg(c.raw_payment_value), 2)     AS delivered_aov,
        CASE
            WHEN sum(c.payment_value) >= 1000 THEN 'VIP (>= 1,000 R$)'
            WHEN sum(c.payment_value) >= 500  THEN 'High [500 - 1,000) R$'
            WHEN sum(c.payment_value) >= 100  THEN 'Medium [100 - 500) R$'
            ELSE 'Standard (< 100 R$)'
        END                                    AS spending_tier
    FROM valid_customer_orders AS c
    JOIN customer_latest_address AS a
        ON a.customer_unique_id = c.customer_unique_id
    GROUP BY c.customer_unique_id, a.latest_customer_state, a.latest_customer_city
)
SELECT
    customer_unique_id,
    spending_tier,
    latest_customer_state,
    latest_customer_city,
    delivered_orders,
    first_purchase_date,
    last_purchase_date,
    round(monetary_value, 2)                   AS customer_monetary_value,
    round(delivered_aov, 2)                    AS customer_delivered_aov
FROM customer_spending_cube
WHERE spending_tier = 'VIP (>= 1,000 R$)'
ORDER BY monetary_value DESC, delivered_orders DESC, customer_unique_id ASC
LIMIT 20;


-- =============================================================================
-- 7b) SLICE (Tổng hợp theo Bang): Cố định lát cắt `spending_tier = 'VIP (>= 1,000 R$)'`
--     và phân tích quy mô theo chiều Địa lý (gắn theo bang tại đơn hàng delivered có ngày đặt hàng gần nhất
--     trên toàn bộ lịch sử đơn delivered của khách hàng `latest_customer_state`, dùng order_id ASC phá hòa ổn định;
--     mỗi khách VIP thuộc duy nhất 1 bang — khác với KPI 3 tính theo bang phát sinh giao dịch của từng đơn hàng).
--     `spending_tier` được tính trên TỔNG CHI TIÊU TOÀN KHO của khách hàng.
--     Lưu ý phương pháp luận:
--       - `vip_delivered_orders` và `vip_monetary_value` là tổng hợp toàn bộ lịch sử đơn delivered của các khách VIP
--         được phân vào từng bang (theo địa chỉ tại đơn có ngày đặt gần nhất), KHÔNG chỉ là số đơn và giá trị thanh toán phát sinh tại bang đó.
--       - Cột `pct_of_total_vip_spend` được làm tròn 2 chữ số thập phân; không cộng gộp các tỷ lệ đã làm tròn này để kết luận tổng phải bằng đúng 100,00% (do sai số làm tròn số học thông thường).
-- =============================================================================
WITH customer_latest_address AS (
    SELECT customer_unique_id, customer_state AS latest_customer_state
    FROM (
        SELECT
            customer_unique_id,
            customer_state,
            row_number() OVER (
                PARTITION BY customer_unique_id
                ORDER BY purchase_date DESC, order_id ASC
            ) AS rn
        FROM valid_customer_orders
    ) t
    WHERE rn = 1
),
customer_spending_cube AS (
    SELECT
        c.customer_unique_id,
        a.latest_customer_state,
        count(c.order_id)            AS delivered_orders,
        count(c.raw_payment_value)   AS orders_with_payment,
        sum(c.payment_value)         AS vip_spend,
        CASE
            WHEN sum(c.payment_value) >= 1000 THEN 'VIP (>= 1,000 R$)'
            WHEN sum(c.payment_value) >= 500  THEN 'High [500 - 1,000) R$'
            WHEN sum(c.payment_value) >= 100  THEN 'Medium [100 - 500) R$'
            ELSE 'Standard (< 100 R$)'
        END                          AS spending_tier
    FROM valid_customer_orders AS c
    JOIN customer_latest_address AS a
        ON a.customer_unique_id = c.customer_unique_id
    GROUP BY c.customer_unique_id, a.latest_customer_state
)
SELECT
    latest_customer_state,
    spending_tier,
    count(customer_unique_id)                                                AS vip_customers,
    sum(delivered_orders)                                                    AS vip_delivered_orders,
    round(sum(vip_spend), 2)                                                 AS vip_monetary_value,
    round(avg(vip_spend), 2)                                                 AS avg_monetary_per_vip,
    round(sum(vip_spend) / nullif(sum(orders_with_payment), 0), 2)           AS vip_delivered_aov,
    round(100.0 * sum(vip_spend) / sum(sum(vip_spend)) OVER (), 2)           AS pct_of_total_vip_spend
FROM customer_spending_cube
WHERE spending_tier = 'VIP (>= 1,000 R$)'
GROUP BY latest_customer_state, spending_tier
ORDER BY sum(vip_spend) DESC, count(customer_unique_id) DESC, latest_customer_state ASC;


-- =============================================================================
-- 8a) DICE (Trích xuất Sub-cube đa chiều: Địa lý × Thời gian × Nhóm khách mua lặp lại):
--     Theo lý thuyết Chapter 2 Slide 23 & Chapter 3 Slide 26, 38:
--     Lọc đồng thời trên nhiều chiều:
--       (1) Chiều Địa lý: customer_state IN ('SP', 'RJ', 'MG')
--       (2) Chiều Thời gian: year BETWEEN 2017 AND 2018
--       (3) Chiều Phân loại khách: Repeat Buyer (tổng số đơn delivered >= 2 trên toàn kho — Phương án A)
--     Giữ nguyên các trục (customer_state, purchase_year) để hiển thị các cell có dữ liệu phát sinh
--     của Sub-cube (tối đa 3 bang × 2 năm = 6 tổ hợp; trên dữ liệu Olist cả 6 ô đều có giao dịch).
--     LƯU Ý VỀ TÍNH CHẤT CỘNG GỘP CỦA ĐỘ ĐO:
--     Cột `active_repeat_customers_in_cell` (`COUNT(DISTINCT customer_unique_id)`) là
--     ĐỘ ĐO PHI CỘNG GỘP (Non-additive Measure), vì một khách hàng có thể phát sinh đơn hàng
--     ở cả 2 năm (2017, 2018) hoặc ở nhiều bang khác nhau.
--     Tuyệt đối không cộng trực tiếp số khách giữa các ô để suy ra tổng khách duy nhất của toàn Sub-cube
--     (khi cần tổng khách duy nhất, phải thực hiện lại `COUNT(DISTINCT customer_unique_id)` trên toàn tập lọc).
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
    count(DISTINCT v.customer_unique_id)                                     AS active_repeat_customers_in_cell,
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
-- 8b) DICE (Chi tiết Top 20 khách hàng Repeat Buyer toàn kho có giao dịch tại Bang SP ∩ Năm 2017–2018):
--     - Tiêu chí sắp xếp: Top 20 khách hàng mua thường xuyên nhất trong Sub-cube (ưu tiên số đơn hàng giảm dần,
--       sau đó đến tổng giá trị thanh toán giảm dần, phá hòa bằng customer_unique_id ASC).
--     - Đồng bộ 100% với 8a theo Phương án A: Tập `repeat_buyer_dim` xác định trên toàn bộ `valid_customer_orders`
--       (`count(order_id) >= 2`), sau đó phân tích các đơn hàng phát sinh tại `SP` trong giai đoạn `2017–2018`.
--     - Đồng bộ quy ước địa chỉ với 7a, 7b và 10: Hiển thị địa chỉ giao hàng tại đơn delivered
--       có ngày đặt hàng gần nhất trên toàn bộ lịch sử đơn delivered của khách hàng
--       (`latest_customer_state_national`, `latest_customer_city_national`, dùng order_id ASC phá hòa ổn định;
--       tách bạch rõ với bang phát sinh giao dịch của lát cắt `customer_state = 'SP'`).
-- =============================================================================
WITH repeat_buyer_dim AS (
    SELECT customer_unique_id
    FROM valid_customer_orders
    GROUP BY customer_unique_id
    HAVING count(order_id) >= 2
),
customer_latest_address AS (
    SELECT
        customer_unique_id,
        customer_state AS latest_customer_state_national,
        customer_city  AS latest_customer_city_national
    FROM (
        SELECT
            customer_unique_id,
            customer_state,
            customer_city,
            row_number() OVER (
                PARTITION BY customer_unique_id
                ORDER BY purchase_date DESC, order_id ASC
            ) AS rn
        FROM valid_customer_orders
    ) t
    WHERE rn = 1
)
SELECT
    v.customer_unique_id,
    v.customer_state,
    a.latest_customer_state_national,
    a.latest_customer_city_national,
    count(v.order_id)                          AS subcube_delivered_orders,
    min(v.purchase_date)                       AS first_order_date_in_subcube,
    max(v.purchase_date)                       AS last_order_date_in_subcube,
    max(v.purchase_date) - min(v.purchase_date) AS lifespan_days_in_subcube,
    round(sum(v.payment_value), 2)             AS subcube_payment_value,
    round(avg(v.raw_payment_value), 2)         AS subcube_delivered_aov
FROM valid_customer_orders AS v
JOIN repeat_buyer_dim AS r
    ON r.customer_unique_id = v.customer_unique_id
JOIN customer_latest_address AS a
    ON a.customer_unique_id = v.customer_unique_id
WHERE v.customer_state = 'SP'
  AND v.year BETWEEN 2017 AND 2018
GROUP BY
    v.customer_unique_id,
    v.customer_state,
    a.latest_customer_state_national,
    a.latest_customer_city_national
ORDER BY count(v.order_id) DESC, sum(v.payment_value) DESC, v.customer_unique_id ASC
LIMIT 20;


-- =============================================================================
-- 9a) PIVOT: Ma trận 27 Bang (dòng) × 8 Trạng thái đơn (cột) + Giá trị thanh toán delivered
--     Xoay trục (Rotate) chiều `order_status` thành các cột để so sánh vận hành giữa 27 Bang.
--     Lưu ý: Ma trận trả về đúng 27 dòng khi và chỉ khi dữ liệu trong kho chứa đủ 27 đơn vị hành chính
--     của Brazil và không có bản ghi nào bị customer_state IS NULL (qua kiểm chứng thực tế trên kho dữ liệu,
--     toàn bộ 99.441 đơn hàng đều có mã bang hợp lệ thuộc 27 bang, không có NULL).
-- =============================================================================
SELECT
    f.customer_state,
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
-- 9b) PIVOT: Ma trận 5 Bang cố định (SP, RJ, MG, RS, PR) × Chỉ tiêu thanh toán theo 3 Năm (2016..2018)
--     kết hợp Phân phối Quy mô đơn hàng (Discretized Order Size Tiers: <100, 100-500, >=500 R$) toàn kỳ
--     Phân biệt rạch ròi 2 nhóm chỉ tiêu trên mỗi dòng bang:
--       - Nhóm chỉ tiêu theo năm: pay_YYYY và orders_YYYY tính riêng cho từng năm (2016, 2017, 2018).
--       - Nhóm quy mô đơn hàng: orders_under_100, orders_100_to_500, orders_over_500 và orders_missing_payment
--         được tính dồn trên TOÀN BỘ GIAI ĐOẠN 2016–2018 của từng bang (tổng 4 cột này = orders_2016 + orders_2017 + orders_2018).
--     Đồng bộ 5 bang cố định với Pivot của Bạn 2, khóa tường minh 3 năm 2016–2018 trên đơn delivered.
--     Lưu ý: Lọc rõ ràng `raw_payment_value IS NOT NULL` ở cả 3 bậc quy mô để không đếm sai đơn NULL vào nhóm dưới 100 R$.
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
    count(order_id) FILTER (WHERE raw_payment_value IS NOT NULL AND raw_payment_value < 100)
                                                                             AS orders_under_100,
    count(order_id) FILTER (WHERE raw_payment_value IS NOT NULL AND raw_payment_value >= 100 AND raw_payment_value < 500)
                                                                             AS orders_100_to_500,
    count(order_id) FILTER (WHERE raw_payment_value IS NOT NULL AND raw_payment_value >= 500)
                                                                             AS orders_over_500,
    count(order_id) FILTER (WHERE raw_payment_value IS NULL)                 AS orders_missing_payment
FROM valid_customer_orders
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
  AND year IN (2016, 2017, 2018)
GROUP BY customer_state
ORDER BY sum(payment_value) DESC, customer_state ASC;


-- =============================================================================
-- 10) TRUY VẤN NÂNG CAO (Window Functions):
--     Xếp hạng Top 3 khách hàng có giá trị chi tiêu phát sinh lớn nhất trong từng Bang lớn
--     (Top Spenders by Order State) và Phân vị tích lũy chi tiêu toàn quốc (Percentile Profiling)
--     Cơ sở lý thuyết & Ngữ nghĩa dữ liệu:
--       - Phân biệt rõ 2 ngữ nghĩa địa lý trên cùng dòng kết quả:
--         + `customer_state`: Bang phát sinh đơn hàng delivered (dùng để gom `state_spend` và xếp hạng đóng góp doanh số tại bang đó).
--         + `latest_customer_state_national`, `latest_customer_city_national`: Bang và Thành phố giao hàng ở đơn delivered có ngày đặt hàng gần nhất
--           trên toàn kho (Latest Purchase-Date Shipping Address, dùng `order_id ASC` làm khóa phá hòa) của khách hàng đó (có thể khác `customer_state` nếu khách từng nhận hàng ở nhiều bang).
--       - Window Functions trong ROLAP:
--         + `DENSE_RANK() OVER (PARTITION BY customer_state ORDER BY state_spend DESC)`: chỉ sắp theo `state_spend` (đã làm tròn 2 chữ số) để bảo toàn đồng hạng; các khách hàng có cùng giá trị sau làm tròn sẽ được xem là đồng hạng.
--         + `ROW_NUMBER() OVER (... ORDER BY state_spend DESC, state_delivered_orders DESC, customer_unique_id ASC)`: lọc tối đa 3 khách hàng mỗi bang (giới hạn logic tối đa 15 dòng trên 5 bang; kết quả thực tế trên database đạt đủ đúng 15 dòng, 3 khách mỗi bang).
--         + `PERCENT_RANK() OVER (ORDER BY national_total_spend ASC)`: tính trên `national_total_spend` đã làm tròn 2 chữ số (các khách hàng có cùng giá trị sau làm tròn xem như đồng hạng), phản ánh vị thế chi tiêu tương đối toàn quốc, tuyệt đối không phải phân nhóm hay phân khúc tiếp thị.
--       - Toàn bộ mô hình phân khúc RFM, K-Means Clustering, kịch bản What-if và khuyến nghị
--         chiến lược được chuyển trọn vẹn sang Giai đoạn 5 (DSS) theo đúng phân công đề tài.
-- =============================================================================
WITH customer_national_spend AS (
    SELECT
        customer_unique_id,
        round(sum(payment_value), 2) AS national_total_spend
    FROM valid_customer_orders
    GROUP BY customer_unique_id
),
customer_national_percentile AS (
    SELECT
        customer_unique_id,
        national_total_spend,
        round(
            (percent_rank() OVER (ORDER BY national_total_spend ASC) * 100)::numeric,
            2
        ) AS national_spend_percentile
    FROM customer_national_spend
),
customer_latest_address AS (
    SELECT
        customer_unique_id,
        customer_state AS latest_customer_state_national,
        customer_city  AS latest_customer_city_national
    FROM (
        SELECT
            customer_unique_id,
            customer_state,
            customer_city,
            row_number() OVER (
                PARTITION BY customer_unique_id
                ORDER BY purchase_date DESC, order_id ASC
            ) AS rn
        FROM valid_customer_orders
    ) t
    WHERE rn = 1
),
customer_state_spend AS (
    SELECT
        v.customer_unique_id,
        v.customer_state,
        a.latest_customer_state_national,
        a.latest_customer_city_national,
        count(v.order_id)                                  AS state_delivered_orders,
        round(sum(v.payment_value), 2)                     AS state_spend,
        round(avg(v.raw_payment_value), 2)                 AS state_customer_aov
    FROM valid_customer_orders AS v
    JOIN customer_latest_address AS a
        ON a.customer_unique_id = v.customer_unique_id
    GROUP BY
        v.customer_unique_id,
        v.customer_state,
        a.latest_customer_state_national,
        a.latest_customer_city_national
),
ranked_customers AS (
    SELECT
        s.customer_state,
        s.customer_unique_id,
        s.latest_customer_state_national,
        s.latest_customer_city_national,
        s.state_delivered_orders,
        s.state_spend,
        s.state_customer_aov,
        p.national_total_spend,
        dense_rank() OVER (
            PARTITION BY s.customer_state
            ORDER BY s.state_spend DESC
        )                                                  AS state_spend_dense_rank,
        row_number() OVER (
            PARTITION BY s.customer_state
            ORDER BY s.state_spend DESC, s.state_delivered_orders DESC, s.customer_unique_id ASC
        )                                                  AS rank_within_state,
        p.national_spend_percentile
    FROM customer_state_spend AS s
    JOIN customer_national_percentile AS p
        ON p.customer_unique_id = s.customer_unique_id
)
SELECT
    customer_state,
    state_spend_dense_rank,
    rank_within_state,
    customer_unique_id,
    latest_customer_state_national,
    latest_customer_city_national,
    state_delivered_orders,
    state_spend,
    state_customer_aov,
    national_total_spend,
    national_spend_percentile || '%'                       AS national_spend_percentile_pct
FROM ranked_customers
WHERE customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
  AND rank_within_state <= 3
ORDER BY customer_state ASC, rank_within_state ASC;


-- =============================================================================
-- PHỤ LỤC: TRUY VẤN KIỂM CHỨNG SỐ LIỆU ĐỘ ĐO PHI CỘNG GỘP (AUDIT & REPRODUCIBILITY)
-- =============================================================================

-- 11) KIỂM CHỨNG KPI 2: Số khách hàng đa trạng thái đơn hàng (Multi-status Customers)
--     Xác nhận phân tách rạch ròi:
--       + unique_system_customers: 96.096 khách duy nhất toàn hệ thống.
--       + total_customer_status_memberships: 96.300 lượt khách-trạng thái (tổng cộng dọc KPI 2).
--       + multi_status_customers: 203 khách hàng có đơn ở nhiều trạng thái.
--       + extra_customer_status_memberships: 204 lượt phát sinh thêm (96.300 - 96.096 = 204).
-- =============================================================================
WITH customer_status AS (
    SELECT
        c.customer_unique_id,
        count(DISTINCT f.order_status) AS status_count
    FROM dw.fact_customer_order AS f
    JOIN dw.dim_customer AS c
        ON c.customer_key = f.customer_key
    GROUP BY c.customer_unique_id
)
SELECT
    count(*)                                              AS unique_system_customers,
    sum(status_count)                                     AS total_customer_status_memberships,
    count(*) FILTER (WHERE status_count > 1)              AS multi_status_customers,
    sum(status_count - 1) FILTER (WHERE status_count > 1) AS extra_customer_status_memberships
FROM customer_status;


-- =============================================================================
-- 12) KIỂM CHỨNG KPI 3: Phân bố chi tiết số khách hàng theo số bang nhận hàng (Cross-state Breakdown)
--     Xác nhận cụ thể: 1 bang (93.321 khách), 2 bang (36 khách, 36 lượt dư), 3 bang (1 khách, 2 lượt dư ở CE, SC, SP).
--     Cột cross_state_customer_details hiển thị rõ customer_unique_id kèm danh sách bang tương ứng để kiểm chứng trực tiếp.
-- =============================================================================
WITH customer_state_count AS (
    SELECT
        customer_unique_id,
        count(DISTINCT customer_state) AS state_count,
        array_agg(DISTINCT customer_state ORDER BY customer_state) AS states
    FROM valid_customer_orders
    GROUP BY customer_unique_id
)
SELECT
    state_count,
    count(*)                                                    AS customers,
    sum(state_count - 1)                                        AS extra_memberships,
    array_agg(customer_unique_id || ' -> ' || array_to_string(states, ', ') ORDER BY customer_unique_id)
        FILTER (WHERE state_count > 1)                          AS cross_state_customer_details
FROM customer_state_count
GROUP BY state_count
ORDER BY state_count ASC;

