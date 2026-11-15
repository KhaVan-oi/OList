-- Staging cho database olist_dw (kết nối theo .env, xem .env.example).
-- Chạy lại file này sẽ xóa schema staging và tạo lại bảng rỗng.
--
-- raw_*: đủ cột CSV, kiểu TEXT, chưa khóa.
-- stg_*: thuộc tính dùng cho doanh thu, đơn hàng và RFM.

DROP SCHEMA IF EXISTS staging CASCADE;
CREATE SCHEMA staging;

-- Khách hàng
CREATE TABLE staging.raw_customers (
    customer_id TEXT,
    customer_unique_id TEXT,
    customer_zip_code_prefix TEXT,
    customer_city TEXT,
    customer_state TEXT
);

CREATE TABLE staging.stg_customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_unique_id VARCHAR(50) NOT NULL,
    customer_city VARCHAR(100),
    customer_state CHAR(2)
);


-- Đơn hàng
CREATE TABLE staging.raw_orders (
    order_id TEXT,
    customer_id TEXT,
    order_status TEXT,
    order_purchase_timestamp TEXT,
    order_approved_at TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT
);

CREATE TABLE staging.stg_orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    CONSTRAINT fk_stg_orders_customer
        FOREIGN KEY (customer_id) REFERENCES staging.stg_customers (customer_id)
);

-- Sản phẩm
CREATE TABLE staging.raw_products (
    product_id TEXT,
    product_category_name TEXT,
    product_name_lenght TEXT,
    product_description_lenght TEXT,
    product_photos_qty TEXT,
    product_weight_g TEXT,
    product_length_cm TEXT,
    product_height_cm TEXT,
    product_width_cm TEXT
);

CREATE TABLE staging.stg_products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category_name VARCHAR(100)
);

-- Seller
CREATE TABLE staging.raw_sellers (
    seller_id TEXT,
    seller_zip_code_prefix TEXT,
    seller_city TEXT,
    seller_state TEXT
);

CREATE TABLE staging.stg_sellers (
    seller_id VARCHAR(50) PRIMARY KEY
);

-- Bản dịch danh mục
CREATE TABLE staging.raw_category_translation (
    product_category_name TEXT,
    product_category_name_english TEXT
);

CREATE TABLE staging.stg_category_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100) NOT NULL
);

-- Dòng sản phẩm
CREATE TABLE staging.raw_order_items (
    order_id TEXT,
    order_item_id TEXT,
    product_id TEXT,
    seller_id TEXT,
    shipping_limit_date TEXT,
    price TEXT,
    freight_value TEXT
);

CREATE TABLE staging.stg_order_items (
    order_id VARCHAR(50),
    order_item_id INT,
    product_id VARCHAR(50) NOT NULL,
    seller_id VARCHAR(50) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    freight_value NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT fk_stg_items_order
        FOREIGN KEY (order_id) REFERENCES staging.stg_orders (order_id),
    CONSTRAINT fk_stg_items_product
        FOREIGN KEY (product_id) REFERENCES staging.stg_products (product_id),
    CONSTRAINT fk_stg_items_seller
        FOREIGN KEY (seller_id) REFERENCES staging.stg_sellers (seller_id)
);

-- Thanh toán, tách khỏi dòng sản phẩm
CREATE TABLE staging.raw_order_payments (
    order_id TEXT,
    payment_sequential TEXT,
    payment_type TEXT,
    payment_installments TEXT,
    payment_value TEXT
);

CREATE TABLE staging.stg_order_payments (
    order_id VARCHAR(50),
    payment_sequential INT,
    payment_value NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential),
    CONSTRAINT fk_stg_payments_order
        FOREIGN KEY (order_id) REFERENCES staging.stg_orders (order_id)
);
