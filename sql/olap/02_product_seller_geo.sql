-- Chỉ đọc dw. Tập đơn: delivered. Doanh thu: sum(price).
-- N: toàn kho 10 | pivot 5 | mỗi bang 3 | drill-down & slice 1
--
-- CTE không giữ qua nhiều câu trong PostgreSQL, nên dùng TEMP VIEW
-- làm nền chung (cùng nghĩa với CTE valid_sales trong bản mô tả).

DROP VIEW IF EXISTS valid_sales;

CREATE TEMP VIEW valid_sales AS
SELECT
    s.order_id,
    s.order_item_id,
    s.price,
    s.freight_value,
    s.purchase_date_key,
    s.product_key,
    s.seller_key,
    p.product_id,
    COALESCE(
        p.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    sel.seller_id,
    o.customer_state,
    o.customer_city
FROM dw.fact_sales AS s
JOIN dw.fact_customer_order AS o ON o.order_id = s.order_id
JOIN dw.dim_product AS p ON p.product_key = s.product_key
JOIN dw.dim_seller AS sel ON sel.seller_key = s.seller_key
WHERE o.order_status = 'delivered';


-- =============================================================================
-- 0) Kiểm tra nền: tổng doanh thu / cước / số món / số đơn
-- =============================================================================
SELECT
    round(sum(price), 2) AS total_revenue,
    round(sum(freight_value), 2) AS total_freight,
    count(*) AS items_sold,
    count(DISTINCT order_id) AS orders_with_items
FROM valid_sales;


-- =============================================================================
-- 1) Top 10 danh mục theo doanh thu
-- =============================================================================
SELECT
    category,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT order_id) AS orders
FROM valid_sales
GROUP BY category
ORDER BY sum(price) DESC, count(*) DESC, category
LIMIT 10;


-- =============================================================================
-- 2) Top 10 seller theo doanh thu
-- =============================================================================
SELECT
    seller_id,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT order_id) AS orders
FROM valid_sales
GROUP BY seller_id
ORDER BY sum(price) DESC, count(*) DESC, seller_id
LIMIT 10;


-- =============================================================================
-- 3) Pareto trên product_id
--    20% số mã (có ít nhất 1 dòng delivered) chiếm bao nhiêu % doanh thu
-- =============================================================================
WITH product_rev AS (
    SELECT
        product_id,
        sum(price) AS revenue,
        count(*) AS items_sold
    FROM valid_sales
    GROUP BY product_id
),
ranked AS (
    SELECT
        product_id,
        revenue,
        items_sold,
        row_number() OVER (
            ORDER BY revenue DESC, items_sold DESC, product_id
        ) AS rn,
        count(*) OVER () AS n_products,
        sum(revenue) OVER () AS total_revenue,
        sum(revenue) OVER (
            ORDER BY revenue DESC, items_sold DESC, product_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cum_revenue
    FROM product_rev
),
cutoff AS (
    SELECT *
    FROM ranked
    WHERE rn <= ceil(n_products * 0.20)
)
SELECT
    max(n_products) AS n_products,
    count(*) AS n_top_20pct_products,
    round(max(total_revenue), 2) AS total_revenue,
    round(sum(revenue), 2) AS top_20pct_revenue,
    round(100.0 * sum(revenue) / max(total_revenue), 2) AS pct_of_total_revenue
FROM cutoff;


-- =============================================================================
-- 4) Tỷ lệ cước trên giá bán
-- =============================================================================
SELECT
    round(sum(freight_value), 2) AS total_freight,
    round(sum(price), 2) AS total_revenue,
    round(sum(freight_value) / nullif(sum(price), 0), 4) AS freight_to_price_ratio
FROM valid_sales;


-- =============================================================================
-- 5) Số đơn và doanh thu theo bang
-- =============================================================================
SELECT
    customer_state,
    count(DISTINCT order_id) AS orders,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold
FROM valid_sales
GROUP BY customer_state
ORDER BY sum(price) DESC, count(DISTINCT order_id) DESC, customer_state;


-- =============================================================================
-- 6) ROLL-UP: thành phố -> bang -> toàn bộ
--    grouping_state/city = 1 là dòng tổng của mức đó
-- =============================================================================
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
ORDER BY
    grouping(customer_state),
    sum(price) DESC,
    customer_state,
    grouping(customer_city),
    customer_city;


-- =============================================================================
-- 7) DRILL-DOWN: 1 bang doanh thu cao nhất -> danh mục trong bang đó
-- =============================================================================
WITH top_state AS (
    SELECT customer_state
    FROM valid_sales
    WHERE customer_state IS NOT NULL
    GROUP BY customer_state
    ORDER BY sum(price) DESC, count(*) DESC, customer_state
    LIMIT 1
)
SELECT
    v.customer_state,
    v.category,
    round(sum(v.price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT v.order_id) AS orders
FROM valid_sales AS v
JOIN top_state AS t ON t.customer_state = v.customer_state
GROUP BY v.customer_state, v.category
ORDER BY sum(v.price) DESC, count(*) DESC, v.category;


-- =============================================================================
-- 8) SLICE: 1 danh mục doanh thu cao nhất toàn kho (health_beauty)
-- =============================================================================
WITH top_category AS (
    SELECT category
    FROM valid_sales
    GROUP BY category
    ORDER BY sum(price) DESC, count(*) DESC, category
    LIMIT 1
)
SELECT
    v.category,
    v.customer_state,
    round(sum(v.price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT v.order_id) AS orders
FROM valid_sales AS v
JOIN top_category AS c ON c.category = v.category
GROUP BY v.category, v.customer_state
ORDER BY sum(v.price) DESC, count(*) DESC, v.customer_state;


-- =============================================================================
-- 9) DICE: top 10 seller toàn kho ∩ SP/RJ/MG ∩ health_beauty
--     Top 10 lấy trước trên mọi delivered; không xếp hạng lại sau lọc
--     SP, RJ, MG = 3 bang doanh thu cao nhất trên valid_sales
-- =============================================================================
WITH top_sellers AS (
    SELECT seller_id
    FROM valid_sales
    GROUP BY seller_id
    ORDER BY sum(price) DESC, count(*) DESC, seller_id
    LIMIT 10
)
SELECT
    v.seller_id,
    v.customer_state,
    v.category,
    round(sum(v.price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT v.order_id) AS orders
FROM valid_sales AS v
JOIN top_sellers AS t ON t.seller_id = v.seller_id
WHERE v.customer_state IN ('SP', 'RJ', 'MG')
  AND v.category = 'health_beauty'
GROUP BY v.seller_id, v.customer_state, v.category
ORDER BY sum(v.price) DESC, count(*) DESC, v.seller_id, v.customer_state;


-- =============================================================================
-- 10) PIVOT: top 5 danh mục × SP, RJ, MG, RS, PR (ô trống = 0)
-- =============================================================================
WITH top_categories AS (
    SELECT category
    FROM valid_sales
    GROUP BY category
    ORDER BY sum(price) DESC, count(*) DESC, category
    LIMIT 5
)
SELECT
    c.category,
    round(coalesce(sum(v.price) FILTER (WHERE v.customer_state = 'SP'), 0), 2) AS sp,
    round(coalesce(sum(v.price) FILTER (WHERE v.customer_state = 'RJ'), 0), 2) AS rj,
    round(coalesce(sum(v.price) FILTER (WHERE v.customer_state = 'MG'), 0), 2) AS mg,
    round(coalesce(sum(v.price) FILTER (WHERE v.customer_state = 'RS'), 0), 2) AS rs,
    round(coalesce(sum(v.price) FILTER (WHERE v.customer_state = 'PR'), 0), 2) AS pr,
    round(coalesce(sum(v.price) FILTER (
        WHERE v.customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
    ), 0), 2) AS five_states_total
FROM top_categories AS c
LEFT JOIN valid_sales AS v
    ON v.category = c.category
   AND v.customer_state IN ('SP', 'RJ', 'MG', 'RS', 'PR')
GROUP BY c.category
ORDER BY five_states_total DESC, c.category;


-- =============================================================================
-- 11) Top 3 danh mục mỗi bang (ROW_NUMBER)
-- =============================================================================
WITH by_state_cat AS (
    SELECT
        customer_state,
        category,
        round(sum(price), 2) AS revenue,
        count(*) AS items_sold,
        count(DISTINCT order_id) AS orders
    FROM valid_sales
    WHERE customer_state IS NOT NULL
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
WHERE rn <= 3
ORDER BY customer_state, rn;
