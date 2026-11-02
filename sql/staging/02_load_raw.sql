TRUNCATE
    staging.raw_customers,
    staging.raw_orders,
    staging.raw_order_items,
    staging.raw_order_payments,
    staging.raw_products,
    staging.raw_sellers,
    staging.raw_category_translation;

\copy staging.raw_customers FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/olist_customers_dataset.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy staging.raw_orders FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/olist_orders_dataset.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy staging.raw_order_items FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/olist_order_items_dataset.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy staging.raw_order_payments FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/olist_order_payments_dataset.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy staging.raw_products FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/olist_products_dataset.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy staging.raw_sellers FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/olist_sellers_dataset.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy staging.raw_category_translation FROM 'D:/.LEARN/Year_4/Data Warehouses/BTL/BTL/archive/product_category_name_translation.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

