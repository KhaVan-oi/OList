-- Kho dữ liệu trên database olist_dw, schema dw (mô hình sao, Kimball & Ross 2013).
-- Tên file là lịch sử ("dss" = database ban đầu), không liên quan phần DSS nhập hàng.
-- Chạy lại file này sẽ DROP SCHEMA dw CASCADE: mọi view trong dw bị xóa theo; etl_pipeline.py tạo lại view DSS.

DROP SCHEMA IF EXISTS dw CASCADE;
CREATE SCHEMA dw;

-- 1. Dim_Date. date_key = YYYYMMDD
CREATE TABLE dw.dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INT NOT NULL,
    quarter INT NOT NULL,
    month INT NOT NULL,
    day_of_month INT NOT NULL,
    day_of_week INT NOT NULL, -- ISO: 1 = thứ hai ... 7 = chủ nhật
    is_weekend BOOLEAN NOT NULL,

    CONSTRAINT chk_dim_date_month
        CHECK (month BETWEEN 1 AND 12),

    CONSTRAINT chk_dim_date_quarter
        CHECK (quarter BETWEEN 1 AND 4),

    CONSTRAINT chk_dim_date_day_of_week
        CHECK (day_of_week BETWEEN 1 AND 7),

    CONSTRAINT chk_dim_date_consistency
        CHECK (
            year = EXTRACT(YEAR FROM full_date) AND
            quarter = EXTRACT(QUARTER FROM full_date) AND
            month = EXTRACT(MONTH FROM full_date) AND
            day_of_month = EXTRACT(DAY FROM full_date) AND
            day_of_week = EXTRACT(ISODOW FROM full_date) AND
            is_weekend = (EXTRACT(ISODOW FROM full_date) IN (6, 7)) AND
            date_key = (
                EXTRACT(YEAR FROM full_date)::int * 10000 +
                EXTRACT(MONTH FROM full_date)::int * 100 +
                EXTRACT(DAY FROM full_date)::int
            )
        )
);

-- 2. Dim_Customer. Định danh duy nhất theo customer_unique_id
CREATE TABLE dw.dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_unique_id CHAR(32) NOT NULL UNIQUE
);

-- 3. Dim_Product
CREATE TABLE dw.dim_product (
    product_key SERIAL PRIMARY KEY,
    product_id CHAR(32) NOT NULL UNIQUE,
    product_category_name VARCHAR(100),
    product_category_name_english VARCHAR(100)
);

-- 4. Dim_Seller
CREATE TABLE dw.dim_seller (
    seller_key SERIAL PRIMARY KEY,
    seller_id CHAR(32) NOT NULL UNIQUE
);

-- 5. Fact_Customer_Order (Tạo trước để Fact_Sales tham chiếu)
-- Grain: 1 dòng cho mỗi order_id
CREATE TABLE dw.fact_customer_order (
    order_id CHAR(32) PRIMARY KEY,

    customer_key INT NOT NULL,
    purchase_date_key INT NOT NULL,
    approved_date_key INT NULL,

    order_status VARCHAR(20) NOT NULL,
    total_payment_value NUMERIC(12, 2),

    customer_city VARCHAR(100),
    customer_state CHAR(2),

    CONSTRAINT fk_customer_order_customer
        FOREIGN KEY (customer_key)
        REFERENCES dw.dim_customer (customer_key),

    CONSTRAINT fk_customer_order_purchase_date
        FOREIGN KEY (purchase_date_key)
        REFERENCES dw.dim_date (date_key),

    CONSTRAINT fk_customer_order_approved_date
        FOREIGN KEY (approved_date_key)
        REFERENCES dw.dim_date (date_key),

    CONSTRAINT chk_total_payment_nonnegative
        CHECK (
            total_payment_value IS NULL
            OR total_payment_value >= 0
        )
);

-- 6. Fact_Sales
-- Grain: 1 dòng cho mỗi cặp (order_id, order_item_id)
CREATE TABLE dw.fact_sales (
    order_id CHAR(32) NOT NULL,
    order_item_id INT NOT NULL,

    purchase_date_key INT NOT NULL,
    customer_key INT NOT NULL,
    product_key INT NOT NULL,
    seller_key INT NOT NULL,

    price NUMERIC(10, 2) NOT NULL,
    freight_value NUMERIC(10, 2) NOT NULL,

    CONSTRAINT pk_fact_sales
        PRIMARY KEY (order_id, order_item_id),

    CONSTRAINT fk_sales_order
        FOREIGN KEY (order_id)
        REFERENCES dw.fact_customer_order (order_id),

    CONSTRAINT fk_sales_purchase_date
        FOREIGN KEY (purchase_date_key)
        REFERENCES dw.dim_date (date_key),

    CONSTRAINT fk_sales_customer
        FOREIGN KEY (customer_key)
        REFERENCES dw.dim_customer (customer_key),

    CONSTRAINT fk_sales_product
        FOREIGN KEY (product_key)
        REFERENCES dw.dim_product (product_key),

    CONSTRAINT fk_sales_seller
        FOREIGN KEY (seller_key)
        REFERENCES dw.dim_seller (seller_key),

    CONSTRAINT chk_sales_price_nonnegative
        CHECK (price >= 0),

    CONSTRAINT chk_sales_freight_nonnegative
        CHECK (freight_value >= 0)
);
