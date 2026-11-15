-- Không BEGIN/COMMIT ở đây: giao dịch do etl_pipeline.py quản lý (chỉ commit khi nghiệm thu đạt).

TRUNCATE
    staging.stg_order_items,
    staging.stg_order_payments,
    staging.stg_orders,
    staging.stg_customers,
    staging.stg_products,
    staging.stg_sellers,
    staging.stg_category_translation;

INSERT INTO staging.stg_customers (customer_id, customer_unique_id, customer_city, customer_state)
SELECT 
    btrim(customer_id), 
    btrim(customer_unique_id),
    NULLIF(btrim(customer_city), ''),
    NULLIF(btrim(customer_state), '')
FROM staging.raw_customers;


INSERT INTO staging.stg_products (product_id, product_category_name)
SELECT btrim(product_id), NULLIF(btrim(product_category_name), '')
FROM staging.raw_products;

INSERT INTO staging.stg_sellers (seller_id)
SELECT btrim(seller_id)
FROM staging.raw_sellers;

INSERT INTO staging.stg_category_translation (
    product_category_name,
    product_category_name_english
)
SELECT btrim(product_category_name), btrim(product_category_name_english)
FROM staging.raw_category_translation;

INSERT INTO staging.stg_orders (
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at
)
SELECT
    btrim(order_id),
    btrim(customer_id),
    btrim(order_status),
    NULLIF(btrim(order_purchase_timestamp), '')::timestamp,
    NULLIF(btrim(order_approved_at), '')::timestamp
FROM staging.raw_orders;

INSERT INTO staging.stg_order_items (
    order_id,
    order_item_id,
    product_id,
    seller_id,
    price,
    freight_value
)
SELECT
    btrim(order_id),
    btrim(order_item_id)::integer,
    btrim(product_id),
    btrim(seller_id),
    btrim(price)::numeric(10, 2),
    btrim(freight_value)::numeric(10, 2)
FROM staging.raw_order_items;

INSERT INTO staging.stg_order_payments (
    order_id,
    payment_sequential,
    payment_value
)
SELECT
    btrim(order_id),
    btrim(payment_sequential)::integer,
    btrim(payment_value)::numeric(10, 2)
FROM staging.raw_order_payments;

DO $$
DECLARE
    pair record;
BEGIN
    FOR pair IN
        SELECT 'customers' AS name, (SELECT count(*) FROM staging.raw_customers) AS raw_count, (SELECT count(*) FROM staging.stg_customers) AS stg_count
        UNION ALL
        SELECT 'orders', (SELECT count(*) FROM staging.raw_orders), (SELECT count(*) FROM staging.stg_orders)
        UNION ALL
        SELECT 'order_items', (SELECT count(*) FROM staging.raw_order_items), (SELECT count(*) FROM staging.stg_order_items)
        UNION ALL
        SELECT 'order_payments', (SELECT count(*) FROM staging.raw_order_payments), (SELECT count(*) FROM staging.stg_order_payments)
        UNION ALL
        SELECT 'products', (SELECT count(*) FROM staging.raw_products), (SELECT count(*) FROM staging.stg_products)
        UNION ALL
        SELECT 'sellers', (SELECT count(*) FROM staging.raw_sellers), (SELECT count(*) FROM staging.stg_sellers)
        UNION ALL
        SELECT 'category_translation', (SELECT count(*) FROM staging.raw_category_translation), (SELECT count(*) FROM staging.stg_category_translation)
    LOOP
        IF pair.raw_count <> pair.stg_count THEN
            RAISE EXCEPTION 'So dong % khong khop: raw % , typed %', pair.name, pair.raw_count, pair.stg_count;
        END IF;
    END LOOP;
END $$;
