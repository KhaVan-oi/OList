import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from db_connect import get_db_config, query_df, test_connection


def main():
    cfg = get_db_config()
    print(f"Kiểm tra kết nối tới {cfg['database']} ({cfg['host']}:{cfg['port']})...")
    if not test_connection():
        return

    print("\n" + "=" * 65)
    print("1. TOP 5 DANH MỤC CÓ DOANH THU CAO NHẤT (fact_sales & dim_product)")
    print("=" * 65)
    sql_top_categories = """
        SELECT 
            COALESCE(p.product_category_name_english, p.product_category_name, 'Unknown') AS category,
            count(*) AS items_sold,
            round(sum(f.price), 2) AS total_revenue
        FROM dw.fact_sales f
        JOIN dw.dim_product p ON p.product_key = f.product_key
        GROUP BY category
        ORDER BY total_revenue DESC
        LIMIT 5;
    """
    df_cat = query_df(sql_top_categories)
    print(df_cat.to_string(index=False))

    print("\n" + "=" * 65)
    print("2. PHÂN TÍCH DOANH THU & SỐ ĐƠN THEO KHU VỰC (customer_state từ Fact_Customer_Order)")
    print("=" * 65)
    sql_geo = """
        SELECT 
            f.customer_state,
            count(f.order_id) AS total_orders,
            round(sum(f.total_payment_value), 2) AS total_payment,
            round(avg(f.total_payment_value), 2) AS aov
        FROM dw.fact_customer_order f
        WHERE f.order_status = 'delivered'
        GROUP BY f.customer_state
        ORDER BY total_orders DESC
        LIMIT 5;
    """
    df_geo = query_df(sql_geo)
    print(df_geo.to_string(index=False))

    print("\n" + "=" * 65)
    print("3. PHÂN KHÚC KHÁCH HÀNG RFM (Gom nhóm theo customer_unique_id từ Dim_Customer)")
    print("=" * 65)
    sql_rfm = """
        WITH max_date AS (
            SELECT max(d.full_date) AS snap_date FROM dw.dim_date d
        ),
        customer_rfm AS (
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
        )
        SELECT *
        FROM customer_rfm
        ORDER BY monetary DESC
        LIMIT 5;
    """
    df_rfm = query_df(sql_rfm)
    print(df_rfm.to_string(index=False))

if __name__ == "__main__":
    main()
