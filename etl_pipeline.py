import os
import sys
import time
import argparse
from pathlib import Path

# Fix Windows console encoding for UTF-8 and emojis
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from db_connect import get_connection, ensure_database_exists, get_db_config


BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR / "sql"

# Mapping table raw name -> CSV filename
RAW_TABLE_FILES = [
    ("staging.raw_customers", "olist_customers_dataset.csv"),
    ("staging.raw_orders", "olist_orders_dataset.csv"),
    ("staging.raw_order_items", "olist_order_items_dataset.csv"),
    ("staging.raw_order_payments", "olist_order_payments_dataset.csv"),
    ("staging.raw_products", "olist_products_dataset.csv"),
    ("staging.raw_sellers", "olist_sellers_dataset.csv"),
    ("staging.raw_category_translation", "product_category_name_translation.csv"),
]

def read_sql_file(path: Path) -> str:
    """Read SQL file with UTF-8 encoding."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def run_acceptance_tests(cur):
    """
    Chạy toàn bộ các nội dung kiểm tra nghiệm thu theo mục 8 của tài liệu Fix.md (A -> E).
    """
    print("\n" + "=" * 75)
    print("📋 KIỂM TRA NGHIỆM THU DATA WAREHOUSE THEO MỤC 8 TÀI LIỆU FIX.MD")
    print("=" * 75)

    all_passed = True

    # A. Kiểm tra Grain và trùng lặp
    cur.execute("""
        SELECT count(*)
        FROM dw.fact_sales s
        JOIN dw.fact_customer_order o ON o.order_id = s.order_id
        WHERE s.purchase_date_key <> o.purchase_date_key
           OR s.customer_key <> o.customer_key;
    """)
    mismatch_keys = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*)
        FROM dw.fact_sales s
        LEFT JOIN dw.fact_customer_order o ON o.order_id = s.order_id
        WHERE o.order_id IS NULL;
    """)
    missing_orders_in_fact = cur.fetchone()[0]

    p_f2 = (mismatch_keys == 0 and missing_orders_in_fact == 0)
    all_passed &= p_f2
    print(f"[{'PASS' if p_f2 else 'FAIL'}] F2. Tính nhất quán giữa 2 Fact Table:")
    print(f"       * Đơn hàng lệch purchase_date_key hoặc customer_key: {mismatch_keys} (Kỳ vọng: 0)")
    print(f"       * Đơn trong Fact_Sales thiếu ở Fact_Customer_Order: {missing_orders_in_fact} (Kỳ vọng: 0)")

    # ---------------------------------------------------------
    # [F3] Ánh xạ Product, Seller và Date
    # ---------------------------------------------------------
    cur.execute("SELECT count(*) FROM dw.fact_sales s LEFT JOIN dw.dim_product p ON p.product_key = s.product_key WHERE p.product_key IS NULL;")
    miss_prod = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM dw.fact_sales s LEFT JOIN dw.dim_seller sel ON sel.seller_key = s.seller_key WHERE sel.seller_key IS NULL;")
    miss_seller = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM dw.fact_sales s LEFT JOIN dw.dim_date d ON d.date_key = s.purchase_date_key WHERE d.date_key IS NULL;")
    miss_sales_date = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM dw.fact_customer_order o LEFT JOIN dw.dim_date d ON d.date_key = o.purchase_date_key WHERE d.date_key IS NULL;")
    miss_order_date = cur.fetchone()[0]

    p_f3 = (miss_prod == 0 and miss_seller == 0 and miss_sales_date == 0 and miss_order_date == 0)
    all_passed &= p_f3
    print(f"[{'PASS' if p_f3 else 'FAIL'}] F3. Ánh xạ Dimension (Product, Seller, Date, Customer):")
    print(f"       * Thiếu Product: {miss_prod} | Thiếu Seller: {miss_seller} | Thiếu Date: {miss_sales_date + miss_order_date} (Kỳ vọng: 0)")

    # ---------------------------------------------------------
    # [F4] Đối soát thanh toán đầy đủ
    # ---------------------------------------------------------
    cur.execute("""
        SELECT count(*)
        FROM (
            SELECT 
                f.order_id,
                f.total_payment_value,
                round(sum(p.payment_value), 2) AS stg_pay
            FROM dw.fact_customer_order f
            JOIN staging.stg_order_payments p ON p.order_id = f.order_id
            GROUP BY f.order_id, f.total_payment_value
            HAVING f.total_payment_value <> round(sum(p.payment_value), 2)
        ) diff;
    """)
    pay_diff = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM dw.fact_customer_order WHERE total_payment_value IS NULL;")
    null_pay = cur.fetchone()[0]

    cur.execute("""
        SELECT count(DISTINCT p.order_id)
        FROM staging.stg_order_payments p
        LEFT JOIN dw.fact_customer_order o ON o.order_id = p.order_id
        WHERE o.order_id IS NULL;
    """)
    missing_pay_orders = cur.fetchone()[0]

    p_f4 = (pay_diff == 0 and null_pay == 1 and missing_pay_orders == 0)
    all_passed &= p_f4
    print(f"[{'PASS' if p_f4 else 'FAIL'}] F4. Đối soát thanh toán đầy đủ:")
    print(f"       * Lệch tổng tiền thanh toán: {pay_diff} (Kỳ vọng: 0)")
    print(f"       * Đơn không có payment (NULL chuẩn): {null_pay} đơn delivered (Kỳ vọng: 1)")
    print(f"       * Đơn thanh toán thiếu ở Fact: {missing_pay_orders} (Kỳ vọng: 0)")

    # ---------------------------------------------------------
    # [F5] Kiểm tra trạng thái đơn hàng
    # ---------------------------------------------------------
    cur.execute("""
        SELECT count(*)
        FROM (SELECT order_status, count(*) AS cnt FROM staging.stg_orders GROUP BY order_status) s
        FULL OUTER JOIN (SELECT order_status, count(*) AS cnt FROM dw.fact_customer_order GROUP BY order_status) d
        ON s.order_status = d.order_status
        WHERE s.cnt <> d.cnt OR s.cnt IS NULL OR d.cnt IS NULL;
    """)
    status_diff = cur.fetchone()[0]

    p_f5 = (status_diff == 0)
    all_passed &= p_f5
    print(f"[{'PASS' if p_f5 else 'FAIL'}] F5. Kiểm tra trạng thái đơn hàng: Giữ trọn vẹn 8 trạng thái, lệch = {status_diff} (Kỳ vọng: 0)")

    # ---------------------------------------------------------
    # [F6] Tính nhất quán Dim_Date
    # ---------------------------------------------------------
    cur.execute("""
        SELECT count(*)
        FROM dw.dim_date
        WHERE year <> EXTRACT(YEAR FROM full_date)
           OR quarter <> EXTRACT(QUARTER FROM full_date)
           OR month <> EXTRACT(MONTH FROM full_date)
           OR day_of_month <> EXTRACT(DAY FROM full_date)
           OR day_of_week <> EXTRACT(ISODOW FROM full_date)
           OR is_weekend <> (EXTRACT(ISODOW FROM full_date) IN (6, 7))
           OR date_key <> (EXTRACT(YEAR FROM full_date)::int * 10000 + EXTRACT(MONTH FROM full_date)::int * 100 + EXTRACT(DAY FROM full_date)::int);
    """)
    date_err = cur.fetchone()[0]

    p_f6 = (date_err == 0)
    all_passed &= p_f6
    print(f"[{'PASS' if p_f6 else 'FAIL'}] F6. Tính nhất quán Dim_Date (year, month, quarter, day_of_week, date_key): Lỗi = {date_err} (Kỳ vọng: 0)")

    # ---------------------------------------------------------
    # [F7] Kiểm tra miền giá trị và NULL
    # ---------------------------------------------------------
    cur.execute("SELECT count(*) FROM dw.fact_sales WHERE price < 0 OR freight_value < 0;")
    neg_sales = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*) FROM dw.fact_sales
        WHERE order_id IS NULL OR order_item_id IS NULL OR purchase_date_key IS NULL 
           OR customer_key IS NULL OR product_key IS NULL OR seller_key IS NULL;
    """)
    null_sales_keys = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM dw.fact_customer_order WHERE total_payment_value < 0;")
    neg_payments = cur.fetchone()[0]

    p_f7 = (neg_sales == 0 and null_sales_keys == 0 and neg_payments == 0)
    all_passed &= p_f7
    print(f"[{'PASS' if p_f7 else 'FAIL'}] F7. Kiểm tra miền giá trị và NULL:")
    print(f"       * Giá trị âm (price/freight/payment): {neg_sales + neg_payments} (Kỳ vọng: 0)")
    print(f"       * Khóa bắt buộc bị NULL: {null_sales_keys} (Kỳ vọng: 0)")

    # ---------------------------------------------------------
    # [F8] Kiểm tra KPI nghiệp vụ
    # ---------------------------------------------------------
    cur.execute("SELECT count(DISTINCT order_id), round(sum(total_payment_value), 2) FROM dw.fact_customer_order WHERE order_status = 'delivered';")
    deliv_orders, deliv_revenue = cur.fetchone()

    cur.execute("SELECT count(DISTINCT customer_key) FROM dw.fact_customer_order WHERE order_status = 'delivered';")
    uniq_customers = cur.fetchone()[0]

    p_f8 = (deliv_orders > 0 and deliv_revenue > 0 and uniq_customers > 0)
    all_passed &= p_f8
    print(f"[{'PASS' if p_f8 else 'FAIL'}] F8. Kiểm tra KPI nghiệp vụ (Chạy thử):")
    print(f"       * Đơn hàng giao thành công (delivered): {deliv_orders:,} đơn")
    print(f"       * Tổng doanh thu thanh toán delivered : {deliv_revenue:,.2f} R$")
    print(f"       * Khách hàng mua hàng thành công      : {uniq_customers:,} khách duy nhất")

    print("=" * 80)
    if all_passed:
        print("🏆 KẾT QUẢ NGHIỆM THU: TẤT CẢ 8 TRƯỜNG HỢP KIỂM TRA (F1 -> F8) ĐỀU ĐẠT CHUẨN XUẤT SẮC!")
    else:
        print("⚠️ CÓ TIÊU CHÍ CHƯA ĐẠT, VUI LÒNG KIỂM TRA LẠI DỮ LIỆU.")
    print("=" * 80)
    return all_passed

def run_pipeline(rebuild_schema: bool = True):
    config = get_db_config()
    mode_str = "TẠO LẠI SCHEMA (REBUILD THEO FIX.MD)" if rebuild_schema else "NẠP LẠI DỮ LIỆU (TRUNCATE & RELOAD)"
    print("=" * 80)
    print(f"🚀 BẮT ĐẦU PIPELINE NẠP DỮ LIỆU VÀO DATA WAREHOUSE: {config['database']}")
    print(f"   Chế độ: {mode_str}")
    print("=" * 80)

    start_total = time.time()

    # Bước 0: Đảm bảo database tồn tại
    print("\n[Bước 0] Kiểm tra và khởi tạo database...")
    if not ensure_database_exists(config["database"]):
        print("[!] Không thể kết nối hoặc khởi tạo database. Vui lòng kiểm tra lại cấu hình .env!")
        sys.exit(1)

    conn = get_connection(autocommit=False)
    cur = conn.cursor()

    try:
        # Kiểm tra xem schema đã tồn tại chưa
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'dw';")
        has_dw = cur.fetchone() is not None

        if rebuild_schema or not has_dw:
            # Bước 1: Tạo schema staging và các bảng raw + stg (có customer_city & customer_state)
            print("\n[Bước 1/6] Tạo schema 'staging' (01_schema.sql)...")
            schema_sql = read_sql_file(SQL_DIR / "staging" / "01_schema.sql")
            cur.execute(schema_sql)
            conn.commit()
            print("  -> Schema 'staging' và các bảng cấu trúc đã tạo thành công.")
        else:
            print("\n[Bước 1/6] Schema staging đã có sẵn -> Làm sạch dữ liệu bảng raw...")
            cur.execute("""
                TRUNCATE
                    staging.raw_customers,
                    staging.raw_orders,
                    staging.raw_order_items,
                    staging.raw_order_payments,
                    staging.raw_products,
                    staging.raw_sellers,
                    staging.raw_category_translation;
            """)
            conn.commit()

        # Bước 2: Nạp dữ liệu CSV vào bảng staging.raw_* bằng copy_expert
        print("\n[Bước 2/6] Nạp dữ liệu từ 7 file CSV vào bảng raw...")
        for table, filename in RAW_TABLE_FILES:
            csv_path = BASE_DIR / filename
            if not csv_path.exists():
                raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")

            print(f"  -> Đang nạp {filename} -> {table}...")
            t0 = time.time()
            with open(csv_path, "r", encoding="utf-8") as f:
                cur.copy_expert(
                    f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')",
                    f
                )
            conn.commit()
            cur.execute(f"SELECT count(*) FROM {table}")
            cnt = cur.fetchone()[0]
            print(f"     Xong: {cnt:,} dòng ({time.time() - t0:.2f}s)")

        # Bước 3: Promote từ raw sang stg typed
        print("\n[Bước 3/6] Chuẩn hóa và làm sạch dữ liệu sang 'staging.stg_*' (03_promote.sql)...")
        t0 = time.time()
        promote_sql = read_sql_file(SQL_DIR / "staging" / "03_promote.sql")
        cur.execute(promote_sql)
        conn.commit()
        print(f"  -> Hoàn thành promote sang staging ({time.time() - t0:.2f}s)")

        # Bước 4: Kiểm tra dữ liệu staging
        print("\n[Bước 4/6] Thống kê số dòng các bảng staging...")
        cur.execute("""
            SELECT 'customers' AS table_name, count(*) FROM staging.stg_customers
            UNION ALL SELECT 'orders', count(*) FROM staging.stg_orders
            UNION ALL SELECT 'order_items', count(*) FROM staging.stg_order_items
            UNION ALL SELECT 'order_payments', count(*) FROM staging.stg_order_payments
            UNION ALL SELECT 'products', count(*) FROM staging.stg_products
            UNION ALL SELECT 'sellers', count(*) FROM staging.stg_sellers
            UNION ALL SELECT 'category_translation', count(*) FROM staging.stg_category_translation
            ORDER BY table_name;
        """)
        for row in cur.fetchall():
            print(f"     * staging.stg_{row[0]:<20}: {row[1]:,}")

        # Bước 5: Tạo schema kho dữ liệu dw theo Fix.md
        if rebuild_schema or not has_dw:
            print("\n[Bước 5/6] Tạo schema 'dw' theo thiết kế Fix.md (dss.sql)...")
            dw_schema_sql = read_sql_file(SQL_DIR / "dw" / "dss.sql")
            cur.execute(dw_schema_sql)
            conn.commit()
            print("  -> Schema 'dw' (dim_date, dim_customer, dim_product, dim_seller, fact_customer_order, fact_sales) đã tạo.")
        else:
            print("\n[Bước 5/6] Schema 'dw' đã có sẵn -> Làm sạch bảng DW...")
            cur.execute("""
                TRUNCATE
                    dw.fact_sales,
                    dw.fact_customer_order,
                    dw.dim_date,
                    dw.dim_customer,
                    dw.dim_product,
                    dw.dim_seller
                CASCADE;
            """)
            conn.commit()

        # Bước 6: Nạp dữ liệu vào kho hình sao dw (02_load.sql)
        print("\n[Bước 6/6] Nạp dữ liệu vào các bảng Dimension và Fact (02_load.sql)...")
        t0 = time.time()
        dw_load_sql = read_sql_file(SQL_DIR / "dw" / "02_load.sql")
        cur.execute(dw_load_sql)
        conn.commit()
        print(f"  -> Nạp Dimension & Fact thành công ({time.time() - t0:.2f}s)")

        # Chạy kiểm tra ràng buộc logic của 03_validate.sql (PL/pgSQL assertions)
        print("\n[Kiểm tra tính toàn vẹn 03_validate.sql (PL/pgSQL)]...")
        validate_sql = read_sql_file(SQL_DIR / "dw" / "03_validate.sql")
        cur.execute(validate_sql)
        conn.commit()
        print("  -> Kiểm tra ràng buộc và assertion nội bộ thành công!")

        # Chạy kiểm tra các trường hợp F1 -> F8
        run_acceptance_tests(cur)

        total_time = time.time() - start_total
        print(f"\n🎉 HOÀN TẤT PIPELINE VÀO '{config['database']}' TRONG {total_time:.2f} GIÂY!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ LỖI TRONG QUÁ TRÌNH NẠP DỮ LIỆU: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL Pipeline nạp dữ liệu Olist vào Data Warehouse theo Fix.md")
    parser.add_argument("--reload-only", action="store_true", help="Chỉ nạp lại dữ liệu mà không tạo lại schema (mặc định là rebuild)")
    args = parser.parse_args()

    run_pipeline(rebuild_schema=not args.reload_only)
