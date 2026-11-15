-- Bộ kiểm tra nghiệm thu Data Warehouse sau khi nạp. ĐÂY LÀ NGUỒN KIỂM TRA DUY NHẤT:
-- etl_pipeline.run_acceptance_tests() chạy file này rồi chỉ in báo cáo số liệu.
--   F1..F7: khối DO bên dưới, sai một điều là RAISE EXCEPTION và cả giao dịch bị hủy.
--   F8    : các câu SELECT cuối file, báo cáo KPI để người đọc tự đối chiếu.
-- Nguyên tắc: kiểm tra BẤT BIẾN (khóa, đối soát tổng, miền giá trị), không gõ cứng số đếm của bộ dữ liệu.
-- So sánh hai giá trị dùng IS DISTINCT FROM thay cho <>: <> trả NULL khi một vế NULL (ví dụ tổng của bảng rỗng)
-- nên điều kiện IF không bao giờ đúng và lỗi bị bỏ lọt.

DO $$
DECLARE
    -- Hạng mục A & F2: Grain, dòng & Khóa ngoại
    dup_sales_grain bigint;
    sales_count bigint;
    stg_items_count bigint;
    order_fact_count bigint;
    stg_orders_count bigint;
    missing_order_in_fact bigint;

    -- Hạng mục F1: Doanh số & Phí vận chuyển
    sales_price numeric;
    stg_price numeric;
    sales_freight numeric;
    stg_freight numeric;

    -- Hạng mục F2: Nhất quán giữa 2 Fact
    date_mismatch_facts bigint;
    cust_mismatch_facts bigint;

    -- Hạng mục B & F3: Ánh xạ Dimension (Product, Seller, Date, Customer)
    missing_cust_in_order bigint;
    missing_cust_in_sales bigint;
    missing_prod_in_sales bigint;
    missing_seller_in_sales bigint;
    missing_date_in_sales bigint;
    missing_pdate_in_order bigint;
    missing_adate_in_order bigint;

    -- Hạng mục C: Địa lý
    geo_mismatch bigint;

    -- Hạng mục D & F6: Nhất quán Dim_Date
    date_consistency_err bigint;

    -- Hạng mục E & F4: Thanh toán đầy đủ
    pay_mismatch bigint;
    pay_only_in_stg bigint;
    null_pay_count bigint;
    pay_null_but_in_stg bigint;

    -- Hạng mục F5: Trạng thái đơn hàng
    status_mismatch bigint;

    -- Hạng mục F7: Miền giá trị và NULL
    neg_values bigint;
    null_required_keys bigint;
BEGIN
    -- [F1] Đối soát doanh số và phí vận chuyển
    SELECT round(sum(price), 2), round(sum(freight_value), 2) INTO sales_price, sales_freight FROM dw.fact_sales;
    SELECT round(sum(price), 2), round(sum(freight_value), 2) INTO stg_price, stg_freight FROM staging.stg_order_items;
    IF sales_price IS DISTINCT FROM stg_price OR sales_freight IS DISTINCT FROM stg_freight THEN
        RAISE EXCEPTION 'F1. Lệch tổng tiền: Fact (price: %, freight: %) vs Staging (price: %, freight: %)', 
            sales_price, sales_freight, stg_price, stg_freight;
    END IF;

    -- [F2] Tính nhất quán giữa hai fact table
    SELECT count(*) INTO dup_sales_grain
    FROM (
        SELECT order_id, order_item_id
        FROM dw.fact_sales
        GROUP BY order_id, order_item_id
        HAVING count(*) > 1
    ) t;
    IF dup_sales_grain <> 0 THEN
        RAISE EXCEPTION 'F2. Trùng cặp (order_id, order_item_id) trong Fact_Sales: % dòng', dup_sales_grain;
    END IF;

    SELECT count(*) INTO missing_order_in_fact
    FROM dw.fact_sales s
    LEFT JOIN dw.fact_customer_order o ON o.order_id = s.order_id
    WHERE o.order_id IS NULL;
    IF missing_order_in_fact <> 0 THEN
        RAISE EXCEPTION 'F2. Có % order_id trong Fact_Sales bị thiếu ở Fact_Customer_Order', missing_order_in_fact;
    END IF;

    SELECT count(*) INTO date_mismatch_facts
    FROM dw.fact_sales s
    JOIN dw.fact_customer_order o ON o.order_id = s.order_id
    WHERE s.purchase_date_key IS DISTINCT FROM o.purchase_date_key;
    IF date_mismatch_facts <> 0 THEN
        RAISE EXCEPTION 'F2. Lệch purchase_date_key giữa Fact_Sales và Fact_Customer_Order: % dòng', date_mismatch_facts;
    END IF;

    SELECT count(*) INTO cust_mismatch_facts
    FROM dw.fact_sales s
    JOIN dw.fact_customer_order o ON o.order_id = s.order_id
    WHERE s.customer_key IS DISTINCT FROM o.customer_key;
    IF cust_mismatch_facts <> 0 THEN
        RAISE EXCEPTION 'F2. Lệch customer_key giữa Fact_Sales và Fact_Customer_Order: % dòng', cust_mismatch_facts;
    END IF;

    -- [F3] Ánh xạ Product, Seller, Date và Customer
    SELECT count(*) INTO missing_cust_in_order FROM dw.fact_customer_order f LEFT JOIN dw.dim_customer c ON c.customer_key = f.customer_key WHERE c.customer_key IS NULL;
    SELECT count(*) INTO missing_cust_in_sales FROM dw.fact_sales s LEFT JOIN dw.dim_customer c ON c.customer_key = s.customer_key WHERE c.customer_key IS NULL;
    SELECT count(*) INTO missing_prod_in_sales FROM dw.fact_sales s LEFT JOIN dw.dim_product p ON p.product_key = s.product_key WHERE p.product_key IS NULL;
    SELECT count(*) INTO missing_seller_in_sales FROM dw.fact_sales s LEFT JOIN dw.dim_seller sel ON sel.seller_key = s.seller_key WHERE sel.seller_key IS NULL;
    SELECT count(*) INTO missing_date_in_sales FROM dw.fact_sales s LEFT JOIN dw.dim_date d ON d.date_key = s.purchase_date_key WHERE d.date_key IS NULL;
    SELECT count(*) INTO missing_pdate_in_order FROM dw.fact_customer_order o LEFT JOIN dw.dim_date d ON d.date_key = o.purchase_date_key WHERE d.date_key IS NULL;
    SELECT count(*) INTO missing_adate_in_order FROM dw.fact_customer_order o LEFT JOIN dw.dim_date d ON d.date_key = o.approved_date_key WHERE o.approved_date_key IS NOT NULL AND d.date_key IS NULL;

    IF (missing_cust_in_order + missing_cust_in_sales + missing_prod_in_sales + missing_seller_in_sales + 
        missing_date_in_sales + missing_pdate_in_order + missing_adate_in_order) <> 0 THEN
        RAISE EXCEPTION 'F3. Lỗi ánh xạ khóa ngoại dimension: cust_ord=%, cust_sales=%, prod=%, seller=%, date_sales=%, pdate_ord=%, adate_ord=%',
            missing_cust_in_order, missing_cust_in_sales, missing_prod_in_sales, missing_seller_in_sales,
            missing_date_in_sales, missing_pdate_in_order, missing_adate_in_order;
    END IF;

    -- [F4] Đối soát thanh toán đầy đủ
    SELECT count(*) INTO pay_mismatch
    FROM (
        SELECT 
            f.order_id,
            f.total_payment_value,
            round(sum(p.payment_value), 2) AS stg_pay
        FROM dw.fact_customer_order f
        JOIN staging.stg_order_payments p ON p.order_id = f.order_id
        GROUP BY f.order_id, f.total_payment_value
        HAVING f.total_payment_value IS DISTINCT FROM round(sum(p.payment_value), 2)
    ) diff;
    IF pay_mismatch <> 0 THEN
        RAISE EXCEPTION 'F4. Có % đơn hàng có total_payment_value lệch với sum(payment_value)', pay_mismatch;
    END IF;

    SELECT count(DISTINCT p.order_id) INTO pay_only_in_stg
    FROM staging.stg_order_payments p
    LEFT JOIN dw.fact_customer_order o ON o.order_id = p.order_id
    WHERE o.order_id IS NULL;
    IF pay_only_in_stg <> 0 THEN
        RAISE EXCEPTION 'F4. Có % đơn hàng có thanh toán nhưng không tồn tại trong Fact_Customer_Order', pay_only_in_stg;
    END IF;

    -- Bất biến: NULL ở total_payment_value nghĩa là nguồn THỰC SỰ không có dòng thanh toán,
    -- không phải do nạp thiếu. Không gõ cứng số lượng (bộ Olist hiện có 1 đơn như vậy) vì đó là
    -- đặc điểm của dữ liệu, không phải quy tắc; số này chỉ được báo bằng NOTICE.
    SELECT count(*) INTO pay_null_but_in_stg
    FROM dw.fact_customer_order f
    WHERE f.total_payment_value IS NULL
      AND EXISTS (SELECT 1 FROM staging.stg_order_payments p WHERE p.order_id = f.order_id);
    IF pay_null_but_in_stg <> 0 THEN
        RAISE EXCEPTION 'F4. Có % đơn bị NULL thanh toán dù staging có dòng thanh toán', pay_null_but_in_stg;
    END IF;

    SELECT count(*) INTO null_pay_count
    FROM dw.fact_customer_order
    WHERE total_payment_value IS NULL;
    RAISE NOTICE 'F4. Số đơn không có dòng thanh toán ở nguồn (để NULL, không gán 0): %', null_pay_count;

    -- [F5] Kiểm tra trạng thái đơn hàng (đảm bảo không mất / lọc nhầm)
    SELECT count(*) INTO status_mismatch
    FROM (
        SELECT s.order_status, s.cnt AS sc, d.cnt AS dc
        FROM (SELECT order_status, count(*) AS cnt FROM staging.stg_orders GROUP BY order_status) s
        FULL JOIN (SELECT order_status, count(*) AS cnt FROM dw.fact_customer_order GROUP BY order_status) d
        ON d.order_status = s.order_status
        WHERE s.cnt IS DISTINCT FROM d.cnt
    ) t;
    IF status_mismatch <> 0 THEN
        RAISE EXCEPTION 'F5. Có trạng thái đơn hàng bị lệch số lượng giữa Staging và Fact: % loại trạng thái', status_mismatch;
    END IF;

    -- [F6] Tính nhất quán Dim_Date
    SELECT count(*) INTO date_consistency_err
    FROM dw.dim_date
    WHERE year IS DISTINCT FROM EXTRACT(YEAR FROM full_date)
       OR quarter IS DISTINCT FROM EXTRACT(QUARTER FROM full_date)
       OR month IS DISTINCT FROM EXTRACT(MONTH FROM full_date)
       OR day_of_month IS DISTINCT FROM EXTRACT(DAY FROM full_date)
       OR day_of_week IS DISTINCT FROM EXTRACT(ISODOW FROM full_date)
       OR is_weekend IS DISTINCT FROM (EXTRACT(ISODOW FROM full_date) IN (6, 7))
       OR date_key IS DISTINCT FROM (EXTRACT(YEAR FROM full_date)::int * 10000 + EXTRACT(MONTH FROM full_date)::int * 100 + EXTRACT(DAY FROM full_date)::int);
    IF date_consistency_err <> 0 THEN
        RAISE EXCEPTION 'F6. Có % bản ghi trong Dim_Date không nhất quán với full_date', date_consistency_err;
    END IF;

    -- [F7] Kiểm tra miền giá trị và NULL
    SELECT count(*) INTO neg_values
    FROM dw.fact_sales
    WHERE price < 0 OR freight_value < 0;
    IF neg_values <> 0 THEN
        RAISE EXCEPTION 'F7. Có % bản ghi trong Fact_Sales có price hoặc freight_value âm', neg_values;
    END IF;

    SELECT count(*) INTO null_required_keys
    FROM (
        SELECT 1 FROM dw.fact_sales WHERE order_id IS NULL OR order_item_id IS NULL OR purchase_date_key IS NULL OR customer_key IS NULL OR product_key IS NULL OR seller_key IS NULL
        UNION ALL
        SELECT 1 FROM dw.fact_customer_order WHERE order_id IS NULL OR customer_key IS NULL OR purchase_date_key IS NULL OR order_status IS NULL
    ) t;
    IF null_required_keys <> 0 THEN
        RAISE EXCEPTION 'F7. Có % bản ghi bị NULL ở các trường khóa bắt buộc', null_required_keys;
    END IF;

    RAISE NOTICE 'F1 -> F7: mọi ràng buộc đều đạt.';
END $$;

-- -------------------------------------------------------------
-- [F8] BÁO CÁO CÁC CHỈ SỐ KPI NGHIỆP VỤ XÁC NHẬN KHO DỮ LIỆU
-- -------------------------------------------------------------

-- 1. Doanh số & Số đơn theo năm (từ Fact_Customer_Order và Dim_Date)
SELECT 
    d.year,
    count(f.order_id) AS total_orders,
    round(sum(f.total_payment_value), 2) AS total_payment,
    round(avg(f.total_payment_value), 2) AS aov
FROM dw.fact_customer_order f
JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
GROUP BY d.year
ORDER BY d.year;

-- 2. Doanh số & Số đơn theo trạng thái đơn hàng
SELECT 
    f.order_status,
    count(f.order_id) AS total_orders,
    round(sum(f.total_payment_value), 2) AS total_payment,
    round(100.0 * count(f.order_id) / (SELECT count(*) FROM dw.fact_customer_order), 2) AS pct_orders
FROM dw.fact_customer_order f
GROUP BY f.order_status
ORDER BY total_orders DESC;

-- 3. Tổng số khách hàng duy nhất (toàn kho và có đơn delivered)
SELECT 
    count(DISTINCT c.customer_unique_id) AS total_unique_customers,
    count(DISTINCT CASE WHEN f.order_status = 'delivered' THEN c.customer_unique_id END) AS delivered_customers
FROM dw.fact_customer_order f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key;

-- 4. Top 5 khách hàng chi tiêu nhiều nhất: recency (ngày, tính từ ngày cuối của dim_date), frequency, monetary
WITH max_date AS (
    SELECT max(full_date) AS snap_date FROM dw.dim_date
)
SELECT 
    c.customer_unique_id,
    (SELECT snap_date FROM max_date) - max(d.full_date) AS recency_days,
    count(f.order_id) AS frequency,
    round(sum(f.total_payment_value), 2) AS monetary
FROM dw.fact_customer_order f
JOIN dw.dim_customer c ON c.customer_key = f.customer_key
JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.order_status = 'delivered'
GROUP BY c.customer_unique_id
ORDER BY monetary DESC
LIMIT 5;
