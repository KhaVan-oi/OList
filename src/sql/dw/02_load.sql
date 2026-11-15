-- Nạp dữ liệu vào Data Warehouse schema dw
-- Thứ tự: Dimension trước -> Fact_Customer_Order -> Fact_Sales

-- 1. Nạp Dim_Date
INSERT INTO dw.dim_date (
    date_key,
    full_date,
    year,
    quarter,
    month,
    day_of_month,
    day_of_week,
    is_weekend
)
SELECT
    (EXTRACT(YEAR FROM d)::int * 10000 + EXTRACT(MONTH FROM d)::int * 100 + EXTRACT(DAY FROM d)::int) AS date_key,
    d::date AS full_date,
    EXTRACT(YEAR FROM d)::int AS year,
    EXTRACT(QUARTER FROM d)::int AS quarter,
    EXTRACT(MONTH FROM d)::int AS month,
    EXTRACT(DAY FROM d)::int AS day_of_month,
    EXTRACT(ISODOW FROM d)::int AS day_of_week,
    EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend
FROM generate_series(
    (SELECT LEAST(min(order_purchase_timestamp), min(order_approved_at))::date FROM staging.stg_orders),
    (SELECT GREATEST(max(order_purchase_timestamp), max(order_approved_at))::date FROM staging.stg_orders),
    INTERVAL '1 day'
) AS calendar(d);

-- 2. Nạp Dim_Customer: mỗi dòng 1 khách hàng duy nhất theo customer_unique_id
INSERT INTO dw.dim_customer (customer_unique_id)
SELECT DISTINCT customer_unique_id
FROM staging.stg_customers
ORDER BY customer_unique_id;

-- 3. Nạp Dim_Product
INSERT INTO dw.dim_product (
    product_id,
    product_category_name,
    product_category_name_english
)
SELECT
    p.product_id,
    p.product_category_name,
    t.product_category_name_english
FROM staging.stg_products AS p
LEFT JOIN staging.stg_category_translation AS t
    ON t.product_category_name = p.product_category_name;

-- 4. Nạp Dim_Seller
INSERT INTO dw.dim_seller (seller_id)
SELECT seller_id
FROM staging.stg_sellers;

-- 5. Nạp Fact_Customer_Order trước Fact_Sales
-- Grain: 1 dòng cho mỗi order_id (toàn bộ 99.441 đơn hàng, lưu order_status & địa lý đơn hàng)
INSERT INTO dw.fact_customer_order (
    order_id,
    customer_key,
    purchase_date_key,
    approved_date_key,
    order_status,
    total_payment_value,
    customer_city,
    customer_state
)
SELECT
    o.order_id,
    c.customer_key,
    to_char(o.order_purchase_timestamp, 'YYYYMMDD')::int AS purchase_date_key,
    CASE 
        WHEN o.order_approved_at IS NOT NULL THEN to_char(o.order_approved_at, 'YYYYMMDD')::int 
        ELSE NULL 
    END AS approved_date_key,
    o.order_status,
    pay.total_payment_value,
    cust.customer_city,
    cust.customer_state
FROM staging.stg_orders AS o
JOIN staging.stg_customers AS cust ON cust.customer_id = o.customer_id
JOIN dw.dim_customer AS c ON c.customer_unique_id = cust.customer_unique_id
LEFT JOIN (
    SELECT order_id, round(sum(payment_value), 2) AS total_payment_value
    FROM staging.stg_order_payments
    GROUP BY order_id
) AS pay ON pay.order_id = o.order_id;

-- 6. Nạp Fact_Sales
-- Grain: 1 dòng cho mỗi cặp (order_id, order_item_id)
-- Tham chiếu Fact_Customer_Order qua order_id
INSERT INTO dw.fact_sales (
    order_id,
    order_item_id,
    purchase_date_key,
    customer_key,
    product_key,
    seller_key,
    price,
    freight_value
)
SELECT
    i.order_id,
    i.order_item_id,
    to_char(o.order_purchase_timestamp, 'YYYYMMDD')::int AS purchase_date_key,
    c.customer_key,
    p.product_key,
    s.seller_key,
    i.price,
    i.freight_value
FROM staging.stg_order_items AS i
JOIN staging.stg_orders AS o ON o.order_id = i.order_id
JOIN staging.stg_customers AS cust ON cust.customer_id = o.customer_id
JOIN dw.dim_customer AS c ON c.customer_unique_id = cust.customer_unique_id
JOIN dw.dim_product AS p ON p.product_id = i.product_id
JOIN dw.dim_seller AS s ON s.seller_id = i.seller_id;
