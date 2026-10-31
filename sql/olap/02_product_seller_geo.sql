-- Chỉ đọc dw. Tập đơn: delivered. Doanh thu: sum(price).
-- N: toàn kho 10 | pivot 5 | mỗi bang 3 | drill-down & slice 1
--
-- CTE không giữ qua nhiều câu trong PostgreSQL, nên dùng TEMP VIEW
-- làm nền chung (cùng nghĩa với CTE valid_sales trong bản mô tả).
--
-- orders = count(DISTINCT order_id) của đúng nhóm trên dòng đó.
-- Không cộng cột orders xuyên seller hoặc xuyên danh mục: một đơn có thể có
-- nhiều seller và nhiều danh mục. Cộng orders theo bang thì được, vì một đơn
-- chỉ một customer_state. ROLLUP tính lại distinct ở từng mức, không cộng
-- số đơn của các dòng con.

DROP VIEW IF EXISTS valid_sales;

CREATE TEMP VIEW valid_sales AS
SELECT
    s.order_id,
    s.price,
    s.freight_value,
    p.product_id,
    COALESCE(
        p.product_category_name_english,
        p.product_category_name,
        'Unknown'
    ) AS category,
    sel.seller_id,
    -- Địa chỉ của từng đơn, không lấy từ dim_customer.
    -- dim_customer là 1 dòng / customer_unique_id. Có khách đặt nhiều đơn
    -- về nhiều thành phố, nhiều bang. Gắn city/state lên dim khách sẽ còn
    -- một địa chỉ và gán nhầm doanh thu các đơn cũ.
    o.customer_state,
    o.customer_city
FROM dw.fact_sales AS s
-- order_id là khóa fact đơn: mỗi dòng bán khớp đúng một đơn, sum(price) không bị nhân.
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
--    orders đúng trên từng danh mục. Không cộng cột này giữa các danh mục.
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
--    orders đúng trên từng seller. Cộng 10 dòng sẽ đếm trùng đơn có nhiều seller.
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
--    Cộng orders các bang = tổng đơn, vì mỗi đơn chỉ một customer_state.
-- =============================================================================
SELECT
    customer_state,
    count(DISTINCT order_id) AS orders,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold
FROM valid_sales
GROUP BY customer_state
ORDER BY sum(price) DESC, count(*) DESC, customer_state;


-- =============================================================================
-- 6) ROLL-UP: thành phố -> bang -> toàn bộ
--    grouping_state/city = 1 là dòng tổng của mức đó
--    orders ở dòng tổng được tính lại bằng count(DISTINCT), không phải cộng
--    orders của các thành phố phía dưới.
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
-- 7) DRILL-DOWN (ngược roll-up, cùng hierarchy địa lý)
--     Nấc 1: toàn bộ → Nấc 2: các bang → Nấc 3: thành phố của mọi bang
-- =============================================================================

-- 7a) Nấc 1 — toàn bộ
SELECT
    '(ALL)' AS geo_level,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT order_id) AS orders
FROM valid_sales;

-- 7b) Nấc 2 — xuống các bang
--     Cùng tập và cùng thứ tự với câu 5: mỗi đơn chỉ một bang.
SELECT
    customer_state,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT order_id) AS orders
FROM valid_sales
WHERE customer_state IS NOT NULL
GROUP BY customer_state
ORDER BY sum(price) DESC, count(*) DESC, customer_state;

-- 7c) Nấc 3 — xuống thành phố của mọi bang (đủ chiều ngược roll-up)
SELECT
    customer_state,
    coalesce(customer_city, '(NULL CITY)') AS customer_city,
    round(sum(price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT order_id) AS orders
FROM valid_sales
WHERE customer_state IS NOT NULL
GROUP BY customer_state, customer_city
ORDER BY
    customer_state,
    sum(price) DESC,
    count(*) DESC,
    customer_city;


-- =============================================================================
-- Tham số slice / dice. Sửa INSERT rồi chạy lại file để cắt lát khác.
-- Mặc định là lát đã chốt cho slide:
--   slice: 1 danh mục (health_beauty = danh mục doanh thu cao nhất)
--   dice:  top 10 seller toàn kho ∩ SP/RJ/MG ∩ health_beauty
-- olap_dice_seller đổ trước, cùng thứ tự với câu 2.
-- Câu 8 và 9 chỉ giao các tập này, không xếp hạng lại.
-- Một dòng olap_slice_category = một slice. Nhiều dòng = nhiều danh mục.
-- =============================================================================
DROP TABLE IF EXISTS olap_slice_category;
CREATE TEMP TABLE olap_slice_category (category text PRIMARY KEY);
INSERT INTO olap_slice_category (category) VALUES ('health_beauty');

DROP TABLE IF EXISTS olap_dice_category;
CREATE TEMP TABLE olap_dice_category (category text PRIMARY KEY);
INSERT INTO olap_dice_category (category) VALUES ('health_beauty');

DROP TABLE IF EXISTS olap_dice_state;
CREATE TEMP TABLE olap_dice_state (customer_state char(2) PRIMARY KEY);
INSERT INTO olap_dice_state (customer_state) VALUES ('SP'), ('RJ'), ('MG');

DROP TABLE IF EXISTS olap_dice_seller;
CREATE TEMP TABLE olap_dice_seller (seller_id text PRIMARY KEY);
INSERT INTO olap_dice_seller (seller_id)
SELECT seller_id
FROM valid_sales
GROUP BY seller_id
ORDER BY sum(price) DESC, count(*) DESC, seller_id
LIMIT 10;


-- =============================================================================
-- 8) SLICE: danh mục trong olap_slice_category
--    Seller bị cộng gộp, mặt cắt còn lại là bang. Trong một danh mục, cộng
--    orders theo bang được vì mỗi đơn chỉ một bang.
-- =============================================================================
SELECT
    v.category,
    v.customer_state,
    round(sum(v.price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT v.order_id) AS orders
FROM valid_sales AS v
JOIN olap_slice_category AS c ON c.category = v.category
GROUP BY v.category, v.customer_state
ORDER BY v.category, sum(v.price) DESC, count(*) DESC, v.customer_state;


-- =============================================================================
-- 9) DICE: giao ba tập đã chọn (seller, bang, danh mục). Không xếp hạng trong câu này.
--     Inner join: seller không có doanh thu trong khối này không hiện (không phải ô 0).
--     orders đúng trên từng dòng seller × bang; không cộng các dòng seller
--     để ra tổng đơn của cả khối.
-- =============================================================================
SELECT
    v.seller_id,
    v.customer_state,
    v.category,
    round(sum(v.price), 2) AS revenue,
    count(*) AS items_sold,
    count(DISTINCT v.order_id) AS orders
FROM valid_sales AS v
JOIN olap_dice_seller AS t ON t.seller_id = v.seller_id
JOIN olap_dice_state AS st ON st.customer_state = v.customer_state
JOIN olap_dice_category AS c ON c.category = v.category
GROUP BY v.seller_id, v.customer_state, v.category
ORDER BY v.category, sum(v.price) DESC, count(*) DESC, v.seller_id, v.customer_state;


-- =============================================================================
-- 10) PIVOT: top 5 danh mục × SP, RJ, MG, RS, PR (ô trống = 0)
--     Top 5 chọn theo doanh thu toàn kho, rồi mới xoay bang thành cột.
--     Năm bang là bộ cố định nhiều khách (SP, RJ, MG, RS, PR), không phải
--     top 5 doanh thu. five_states_total chỉ là tổng 5 cột đang hiện.
--     ORDER BY five_states_total có thể khác thứ hạng toàn kho.
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
--     rn là thứ hạng trong bang, không phải hạng toàn kho. Hòa doanh thu
--     vẫn mỗi danh mục một rn. Bang ít hơn 3 danh mục thì ít hơn 3 dòng.
--     Không cộng orders của 3 danh mục trong cùng một bang.
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
