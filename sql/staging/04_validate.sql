SELECT 'customers' AS table_name, count(*) AS row_count FROM staging.stg_customers
UNION ALL
SELECT 'orders', count(*) FROM staging.stg_orders
UNION ALL
SELECT 'order_items', count(*) FROM staging.stg_order_items
UNION ALL
SELECT 'order_payments', count(*) FROM staging.stg_order_payments
UNION ALL
SELECT 'products', count(*) FROM staging.stg_products
UNION ALL
SELECT 'sellers', count(*) FROM staging.stg_sellers
UNION ALL
SELECT 'category_translation', count(*) FROM staging.stg_category_translation
ORDER BY table_name;

SELECT
    p.product_category_name,
    count(*) AS product_rows
FROM staging.stg_products AS p
LEFT JOIN staging.stg_category_translation AS t
    ON t.product_category_name = p.product_category_name
WHERE p.product_category_name IS NOT NULL
  AND t.product_category_name IS NULL
GROUP BY p.product_category_name
ORDER BY p.product_category_name;
