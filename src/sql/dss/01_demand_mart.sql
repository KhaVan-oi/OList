-- DSS: nhu cầu theo tháng × bang × danh mục (đơn delivered).
-- Một view duy nhất làm nguồn cho dự báo nhu cầu và đề xuất lượng nhập hàng.
-- Không đổi schema sao. Chỉ đọc fact_sales, fact_customer_order, dim_product, dim_date.
--
-- Grain: tháng lịch × bang khách (đơn) × danh mục.
--   units   = số dòng hàng (mỗi dòng fact_sales là một món)
--   revenue = sum(price), cùng thước đo "Doanh thu hàng" của OLAP
--   orders  = count(DISTINCT order_id) TRONG ô này. Không cộng xuyên danh mục.
--
-- Được etl_pipeline.py tạo lại sau mỗi lần nạp kho. Đối soát với fact_sales: python run_dss_01.py

CREATE OR REPLACE VIEW dw.v_dss_monthly_demand AS
SELECT
    date_trunc('month', d.full_date)::date AS month_start,
    o.customer_state,
    coalesce(p.product_category_name_english, p.product_category_name, 'Unknown') AS category,
    count(*)                                AS units,
    round(sum(s.price), 2)                  AS revenue,
    count(DISTINCT s.order_id)              AS orders
FROM dw.fact_sales AS s
JOIN dw.fact_customer_order AS o ON o.order_id = s.order_id
JOIN dw.dim_product AS p ON p.product_key = s.product_key
JOIN dw.dim_date AS d ON d.date_key = s.purchase_date_key
WHERE o.order_status = 'delivered'
GROUP BY 1, 2, 3;

COMMENT ON VIEW dw.v_dss_monthly_demand IS
    'DSS nhập hàng: nhu cầu delivered theo tháng, bang, danh mục. Đối soát: sum(revenue) = sum(price) delivered.';
