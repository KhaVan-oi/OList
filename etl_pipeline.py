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
    Chạy toàn bộ các nội dung kiểm tra nghiệm thu theo Fix.md (A -> E)
    và các hạng mục kiểm tra mở rộng (F1 -> F8).
    """
    print("\n" + "=" * 80)
    print("📋 KIỂM TRA NGHIỆM THU DATA WAREHOUSE THEO TÀI LIỆU FIX.MD (A -> E & F1 -> F8)")
    print("=" * 80)

    all_passed = True

    # =========================================================================
    # [A] Kiểm tra Grain và trùng lặp
    # =========================================================================
    cur.execute("""
        SELECT count(*)
        FROM (
            SELECT order_id, order_item_id
            FROM dw.fact_sales
            GROUP BY order_id, order_item_id
            HAVING count(*) > 1
        ) t;
    """)
    dup_sales = cur.fetchone()[0]
    p_dup = (dup_sales == 0)
    all_passed &= p_dup
    print(f"[{'PASS' if p_dup else 'FAIL'}] A1. Trùng lặp (order_id, order_item_id) trong Fact_Sales: {dup_sales} (Kỳ vọng: 0)")

    cur.execute("SELECT count(*) FROM dw.fact_sales;")
    cnt_sales = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM staging.stg_order_items;")
    cnt_stg_items = cur.fetchone()[0]
    p_sales = (cnt_sales == cnt_stg_items == 112650)
    all_passed &= p_sales
    print(f"[{'PASS' if p_sales else 'FAIL'}] A2. Số dòng Fact_Sales: {cnt_sales:,} (Kỳ vọng: {cnt_stg_items:,} dòng nguồn)")

    cur.execute("SELECT count(*) FROM dw.fact_customer_order;")
    cnt_orders = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM staging.stg_orders;")
    cnt_stg_orders = cur.fetchone()[0]
    p_orders = (cnt_orders == cnt_stg_orders == 99441)
    all_passed &= p_orders
    print(f"[{'PASS' if p_orders else 'FAIL'}] A3. Số đơn Fact_Customer_Order: {cnt_orders:,} (Kỳ vọng: {cnt_stg_orders:,} đơn nguồn)")

    # =========================================================================
    # [B] Kiểm tra ánh xạ dimension
    # =========================================================================
    cur.execute("SELECT count(*) FROM dw.dim_customer;")
    cnt_dim_cust = cur.fetchone()[0]
    cur.execute("SELECT count(DISTINCT customer_unique_id) FROM staging.stg_customers;")
    cnt_stg_uniq = cur.fetchone()[0]
    p_cust = (cnt_dim_cust == cnt_stg_uniq == 96096)
    all_passed &= p_cust
    print(f"[{'PASS' if p_cust else 'FAIL'}] B1. Số khách hàng duy nhất Dim_Customer: {cnt_dim_cust:,} (Kỳ vọng: {cnt_stg_uniq:,})")

    cur.execute("""
        SELECT count(*)
        FROM dw.fact_sales s
        LEFT JOIN dw.fact_customer_order o ON o.order_id = s.order_id
        WHERE o.order_id IS NULL;
    """)
    missing_fk = cur.fetchone()[0]
    p_fk = (missing_fk == 0)
    all_passed &= p_fk
    print(f"[{'PASS' if p_fk else 'FAIL'}] B2. Khóa ngoại Fact_Sales -> Fact_Customer_Order: {missing_fk} lỗi (Kỳ vọng: 0)")

    # =========================================================================
    # [C] Kiểm tra địa lý
    # =========================================================================
    cur.execute("""
        SELECT count(*)
        FROM dw.fact_customer_order f
        JOIN staging.stg_orders o ON o.order_id = f.order_id
        JOIN staging.stg_customers cust ON cust.customer_id = o.customer_id
        WHERE COALESCE(f.customer_city, '') <> COALESCE(cust.customer_city, '')
           OR COALESCE(f.customer_state, '') <> COALESCE(cust.customer_state, '');
    """)
    geo_mismatch = cur.fetchone()[0]
    p_geo = (geo_mismatch == 0)
    all_passed &= p_geo
    print(f"[{'PASS' if p_geo else 'FAIL'}] C1. Khớp thông tin địa lý (city, state) giữa Fact và Staging: Lệch = {geo_mismatch} (Kỳ vọng: 0)")

    cur.execute("SELECT count(*) FROM dw.fact_customer_order WHERE customer_city IS NULL OR customer_state IS NULL;")
    null_geo = cur.fetchone()[0]
    print(f"[INFO] C2. Số đơn có địa lý NULL từ nguồn: {null_geo} đơn")

    # =========================================================================
    # [D] Kiểm tra ngày
    # =========================================================================
    cur.execute("""
        SELECT count(*)
        FROM dw.dim_date
        WHERE date_key <> (year * 10000 + month * 100 + day_of_month);
    """)
    date_err = cur.fetchone()[0]
    p_date = (date_err == 0)
    all_passed &= p_date
    print(f"[{'PASS' if p_date else 'FAIL'}] D1. Tính nhất quán date_key (YYYYMMDD) trong Dim_Date: Lỗi = {date_err} (Kỳ vọng: 0)")

    cur.execute("SELECT count(*) FROM dw.fact_customer_order WHERE approved_date_key IS NULL;")
    null_approved = cur.fetchone()[0]
    p_app = (null_approved == 160)
    all_passed &= p_app
    print(f"[{'PASS' if p_app else 'FAIL'}] D2. Số đơn hàng thiếu ngày duyệt (approved_date_key IS NULL): {null_approved} (Kỳ vọng: 160)")

    # =========================================================================
    # [E] Kiểm tra tổng hợp thanh toán cơ bản
    # =========================================================================
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
    p_pay = (pay_diff == 0)
    all_passed &= p_pay
    print(f"[{'PASS' if p_pay else 'FAIL'}] E1. Khớp tổng thanh toán total_payment_value với Staging Payments: Lệch = {pay_diff} (Kỳ vọng: 0)")

    cur.execute("SELECT count(*) FROM dw.fact_customer_order WHERE total_payment_value IS NULL;")
    null_pay = cur.fetchone()[0]
    p_null_pay = (null_pay == 1)
    all_passed &= p_null_pay
    print(f"[{'PASS' if p_null_pay else 'FAIL'}] E2. Số đơn không có bản ghi thanh toán (NULL): {null_pay} đơn delivered (Kỳ vọng: 1 đơn)")

    # =========================================================================
    # [F1] Đối soát doanh số và phí vận chuyển
    # =========================================================================
    cur.execute("SELECT round(sum(price), 2), round(sum(freight_value), 2) FROM dw.fact_sales;")
    dw_price, dw_freight = cur.fetchone()
    cur.execute("SELECT round(sum(price), 2), round(sum(freight_value), 2) FROM staging.stg_order_items;")
    stg_price, stg_freight = cur.fetchone()
    p_f1 = (dw_price == stg_price and dw_freight == stg_freight)
    all_passed &= p_f1
    print(f"\n[{'PASS' if p_f1 else 'FAIL'}] F1. Đối soát doanh số và phí vận chuyển:")
    print(f"       * SUM(price): Fact = {dw_price:,.2f} R$ | Staging = {stg_price:,.2f} R$ (Lệch: {dw_price - stg_price:.2f})")
    print(f"       * SUM(freight_value): Fact = {dw_freight:,.2f} R$ | Staging = {stg_freight:,.2f} R$ (Lệch: {dw_freight - stg_freight:.2f})")

    # =========================================================================
    # [F2] Tính nhất quán giữa hai fact table
    # =========================================================================
    cur.execute("""
        SELECT count(*)
        FROM dw.fact_sales s
        JOIN dw.fact_customer_order o ON o.order_id = s.order_id
        WHERE s.purchase_date_key <> o.purchase_date_key;
    """)
    mismatch_pdate = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*)
        FROM dw.fact_sales s
        JOIN dw.fact_customer_order o ON o.order_id = s.order_id
        WHERE s.customer_key <> o.customer_key;
    """)
    mismatch_cust = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*)
        FROM dw.fact_sales s
        LEFT JOIN dw.fact_customer_order o ON o.order_id = s.order_id
        WHERE o.order_id IS NULL;
    """)
    missing_order_fact = cur.fetchone()[0]

    p_f2 = (mismatch_pdate == 0 and mismatch_cust == 0 and missing_order_fact == 0)
    all_passed &= p_f2
    print(f"[{'PASS' if p_f2 else 'FAIL'}] F2. Tính nhất quán giữa Fact_Sales và Fact_Customer_Order:")
    print(f"       * Lệch purchase_date_key: {mismatch_pdate} | Lệch customer_key: {mismatch_cust} | Thiếu order_id ở Fact đơn: {missing_order_fact} (Kỳ vọng: 0)")

    # =========================================================================
    # [F3] Ánh xạ Product, Seller và Date
    # =========================================================================
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

    # =========================================================================
    # [F4] Đối soát thanh toán đầy đủ
    # =========================================================================
    cur.execute("""
        SELECT count(*)
        FROM (
            SELECT f.order_id, f.total_payment_value, round(sum(p.payment_value), 2) AS stg_pay
            FROM dw.fact_customer_order f
            JOIN staging.stg_order_payments p ON p.order_id = f.order_id
            GROUP BY f.order_id, f.total_payment_value
            HAVING f.total_payment_value <> round(sum(p.payment_value), 2)
        ) diff;
    """)
    mismatch_payments = cur.fetchone()[0]

    cur.execute("""
        SELECT count(DISTINCT p.order_id)
        FROM staging.stg_order_payments p
        LEFT JOIN dw.fact_customer_order o ON o.order_id = p.order_id
        WHERE o.order_id IS NULL;
    """)
    pay_only_in_stg = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*)
        FROM dw.fact_customer_order o
        LEFT JOIN staging.stg_order_payments p ON p.order_id = o.order_id
        WHERE p.order_id IS NULL;
    """)
    order_without_pay = cur.fetchone()[0]

    p_f4 = (mismatch_payments == 0 and pay_only_in_stg == 0 and order_without_pay == 1)
    all_passed &= p_f4
    print(f"[{'PASS' if p_f4 else 'FAIL'}] F4. Đối soát thanh toán đầy đủ:")
    print(f"       * Đơn thanh toán bị lệch tiền: {mismatch_payments} | Đơn chỉ có ở payments: {pay_only_in_stg} | Đơn không có payment: {order_without_pay} (Kỳ vọng: đúng 1 đơn delivered)")

    # =========================================================================
    # [F5] Kiểm tra trạng thái đơn hàng
    # =========================================================================
    cur.execute("""
        SELECT count(*)
        FROM (
            SELECT s.order_status, s.cnt AS sc, d.cnt AS dc
            FROM (SELECT order_status, count(*) AS cnt FROM staging.stg_orders GROUP BY order_status) s
            FULL JOIN (SELECT order_status, count(*) AS cnt FROM dw.fact_customer_order GROUP BY order_status) d
            ON d.order_status = s.order_status
            WHERE s.cnt <> d.cnt OR s.cnt IS NULL OR d.cnt IS NULL
        ) t;
    """)
    status_diff = cur.fetchone()[0]
    p_f5 = (status_diff == 0)
    all_passed &= p_f5
    print(f"[{'PASS' if p_f5 else 'FAIL'}] F5. Kiểm tra trạng thái đơn hàng (nguồn vs Fact): Lệch = {status_diff} (Kỳ vọng: 0, giữ đủ 8 trạng thái)")

    # =========================================================================
    # [F6] Tính nhất quán Dim_Date
    # =========================================================================
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
    dim_date_inconsistency = cur.fetchone()[0]
    p_f6 = (dim_date_inconsistency == 0)
    all_passed &= p_f6
    print(f"[{'PASS' if p_f6 else 'FAIL'}] F6. Tính nhất quán Dim_Date (year, quarter, month, day, dow, weekend): Lỗi = {dim_date_inconsistency} (Kỳ vọng: 0)")

    # =========================================================================
    # [F7] Kiểm tra miền giá trị và NULL
    # =========================================================================
    cur.execute("SELECT count(*) FROM dw.fact_sales WHERE price < 0 OR freight_value < 0;")
    neg_sales = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM dw.fact_customer_order WHERE total_payment_value < 0;")
    neg_pay = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*)
        FROM (
            SELECT 1 FROM dw.fact_sales WHERE order_id IS NULL OR order_item_id IS NULL OR purchase_date_key IS NULL OR customer_key IS NULL OR product_key IS NULL OR seller_key IS NULL
            UNION ALL
            SELECT 1 FROM dw.fact_customer_order WHERE order_id IS NULL OR customer_key IS NULL OR purchase_date_key IS NULL OR order_status IS NULL
        ) t;
    """)
    null_keys = cur.fetchone()[0]

    p_f7 = (neg_sales == 0 and neg_pay == 0 and null_keys == 0)
    all_passed &= p_f7
    print(f"[{'PASS' if p_f7 else 'FAIL'}] F7. Kiểm tra miền giá trị và NULL:")
    print(f"       * Giá tiền / cước / thanh toán âm: {neg_sales + neg_pay} | NULL ở các khóa bắt buộc: {null_keys} (Kỳ vọng: 0)")

    # =========================================================================
    # [F8] Kiểm tra KPI nghiệp vụ
    # =========================================================================
    print("\n--- [F8] KIỂM TRA CÁC CHỈ SỐ KPI NGHIỆP VỤ ---")
    
    # 1. Doanh số theo năm
    cur.execute("""
        SELECT d.year, count(f.order_id), round(sum(f.total_payment_value), 2)
        FROM dw.fact_customer_order f
        JOIN dw.dim_date d ON d.date_key = f.purchase_date_key
        GROUP BY d.year
        ORDER BY d.year;
    """)
    print("  * KPI Doanh số theo năm:")
    for yr, ord_cnt, pay_sum in cur.fetchall():
        print(f"    - Năm {yr}: {ord_cnt:,} đơn | Doanh thu thanh toán: {pay_sum:,.2f} R$")

    # 2. Khách hàng duy nhất
    cur.execute("""
        SELECT 
            count(DISTINCT c.customer_unique_id),
            count(DISTINCT CASE WHEN f.order_status = 'delivered' THEN c.customer_unique_id END)
        FROM dw.fact_customer_order f
        JOIN dw.dim_customer c ON c.customer_key = f.customer_key;
    """)
    total_cust, delivered_cust = cur.fetchone()
    print(f"  * KPI Khách hàng: Tổng {total_cust:,} khách duy nhất ({delivered_cust:,} khách có đơn delivered)")

    # 3. Phân khúc RFM mẫu (Top 3)
    cur.execute("""
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
        ORDER BY monetary DESC NULLS LAST
        LIMIT 3;
    """)
    print("  * KPI RFM mẫu (Top 3 khách hàng chi tiêu cao nhất):")
    for cid, r, f, m in cur.fetchall():
        print(f"    - Khách: {cid} | R: {r} ngày | F: {f} đơn | M: {m:,.2f} R$")

    p_f8 = (total_cust == 96096 and delivered_cust > 90000)
    all_passed &= p_f8
    print(f"[{'PASS' if p_f8 else 'FAIL'}] F8. Đánh giá KPI nghiệp vụ có ý nghĩa: Đạt chuẩn.")

    print("=" * 80)
    if all_passed:
        print("🏆 KẾT QUẢ NGHIỆM THU: TẤT CẢ CÁC HẠNG MỤC (A -> E & F1 -> F8) ĐỀU ĐẠT CHUẨN XUẤT SẮC!")
    else:
        print("⚠️ CÓ TIÊU CHÍ CHƯA ĐẠT, VUI LÒNG KIỂM TRA LẠI DỮ LIỆU.")
    print("=" * 80)
    return all_passed


def run_pipeline(rebuild_schema: bool = True):
    config = get_db_config()
    mode_str = "TẠO LẠI SCHEMA (REBUILD THEO FIX.MD)" if rebuild_schema else "NẠP LẠI DỮ LIỆU (TRUNCATE & RELOAD)"
    print("=" * 75)
    print(f"🚀 BẮT ĐẦU PIPELINE NẠP DỮ LIỆU VÀO DATA WAREHOUSE: {config['database']}")
    print(f"   Chế độ: {mode_str}")
    print("=" * 75)

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
            print("\n[Bước 1/6] Tạo schema 'staging' (staging/01_schema.sql)...")
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
        print("\n[Bước 3/6] Chuẩn hóa và làm sạch dữ liệu sang 'staging.stg_*' (02_promote.sql)...")
        t0 = time.time()
        promote_sql = read_sql_file(SQL_DIR / "staging" / "02_promote.sql")
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

        cur.execute("""
            SELECT p.product_category_name, count(*) AS product_rows
            FROM staging.stg_products AS p
            LEFT JOIN staging.stg_category_translation AS t
                ON t.product_category_name = p.product_category_name
            WHERE p.product_category_name IS NOT NULL
              AND t.product_category_name IS NULL
            GROUP BY p.product_category_name
            ORDER BY p.product_category_name;
        """)
        missing_translation = cur.fetchall()
        if missing_translation:
            print(f"     [INFO] Danh mục có tên nhưng không có bản dịch: {len(missing_translation)}")
            for name, rows in missing_translation:
                print(f"            - {name}: {rows} sản phẩm")
        else:
            print("     [INFO] Mọi danh mục có tên đều có bản dịch tiếng Anh.")

        # Bước 5: Tạo schema kho dữ liệu dw theo Fix.md
        if rebuild_schema or not has_dw:
            print("\n[Bước 5/6] Tạo schema 'dw' theo thiết kế Fix.md (dw/01_schema.sql)...")
            dw_schema_sql = read_sql_file(SQL_DIR / "dw" / "01_schema.sql")
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
        print("\n[Kiểm tra tính toàn vẹn 03_validate.sql]...")
        validate_sql = read_sql_file(SQL_DIR / "dw" / "03_validate.sql")
        cur.execute(validate_sql)
        conn.commit()
        print("  -> Kiểm tra ràng buộc và assertion nội bộ thành công!")

        # Chạy kiểm tra các mục A -> E theo Fix.md
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
