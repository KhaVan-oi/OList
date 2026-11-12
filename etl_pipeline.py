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
    """Nghiệm thu kho sau khi nạp.

    Kiểm tra (F1..F7) chỉ nằm ở sql/dw/03_validate.sql: sai một điều là RAISE EXCEPTION, hàm này ném lỗi theo.
    Phần Python chỉ in số liệu đối soát để người đọc tự so (không lặp lại logic kiểm tra ở hai nơi).
    """
    print("\n" + "=" * 75)
    print("KIỂM TRA NGHIỆM THU DATA WAREHOUSE (sql/dw/03_validate.sql)")
    print("=" * 75)

    notices_before = len(cur.connection.notices)
    cur.execute(read_sql_file(SQL_DIR / "dw" / "03_validate.sql"))
    for notice in cur.connection.notices[notices_before:]:
        print("  " + notice.strip().removeprefix("NOTICE:").strip())

    cur.execute("""
        SELECT
            (SELECT round(sum(price), 2) FROM dw.fact_sales),
            (SELECT round(sum(price), 2) FROM staging.stg_order_items),
            (SELECT round(sum(freight_value), 2) FROM dw.fact_sales),
            (SELECT round(sum(freight_value), 2) FROM staging.stg_order_items),
            (SELECT count(*) FROM dw.fact_sales),
            (SELECT count(*) FROM staging.stg_order_items),
            (SELECT count(*) FROM dw.fact_customer_order),
            (SELECT count(*) FROM staging.stg_orders)
    """)
    f_price, s_price, f_freight, s_freight, f_items, s_items, f_orders, s_orders = cur.fetchone()
    print(f"  F1. price   fact = {f_price:,.2f} | staging = {s_price:,.2f} R$")
    print(f"      freight fact = {f_freight:,.2f} | staging = {s_freight:,.2f} R$")
    print(f"  F2. dòng fact_sales = {f_items:,} / stg_order_items = {s_items:,}; "
          f"đơn fact_customer_order = {f_orders:,} / stg_orders = {s_orders:,}")

    cur.execute("SELECT order_status, count(*) FROM dw.fact_customer_order GROUP BY 1 ORDER BY 2 DESC")
    print("  F5. trạng thái đơn: " + ", ".join(f"{status}={n:,}" for status, n in cur.fetchall()))

    cur.execute("""
        SELECT count(*), round(sum(total_payment_value), 2), count(DISTINCT customer_key)
        FROM dw.fact_customer_order WHERE order_status = 'delivered'
    """)
    deliv_orders, deliv_payment, deliv_customers = cur.fetchone()
    print(f"  F8. delivered: {deliv_orders:,} đơn | thanh toán {deliv_payment:,.2f} R$ | "
          f"{deliv_customers:,} khách duy nhất")

    print("=" * 75)
    print("KẾT QUẢ: F1 -> F7 đạt (03_validate.sql không ném lỗi).")
    print("=" * 75)
    return True


def run_pipeline(rebuild_schema: bool = True):
    config = get_db_config()
    mode_str = "TẠO LẠI SCHEMA (REBUILD)" if rebuild_schema else "NẠP LẠI DỮ LIỆU (TRUNCATE & RELOAD)"
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

        # Bước 5: Tạo schema kho dữ liệu dw
        if rebuild_schema or not has_dw:
            print("\n[Bước 5/6] Tạo schema 'dw' (sql/dw/dss.sql)...")
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

        # Nghiệm thu: 03_validate.sql ném lỗi nếu sai (rollback ở except bên dưới)
        run_acceptance_tests(cur)
        conn.commit()

        # Tạo lại view nguồn cho DSS (bước 5 đã DROP SCHEMA dw CASCADE nên view bị xóa theo).
        # Đối soát view với fact_sales vẫn do run_dss_01.py làm.
        print("\n[Hậu kỳ] Tạo view DSS dw.v_dss_monthly_demand (sql/dss/01_demand_mart.sql)...")
        cur.execute(read_sql_file(SQL_DIR / "dss" / "01_demand_mart.sql"))
        conn.commit()
        print("  -> View DSS đã tạo.")

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
    parser = argparse.ArgumentParser(description="ETL Pipeline nạp dữ liệu Olist vào Data Warehouse")
    parser.add_argument("--reload-only", action="store_true", help="Chỉ nạp lại dữ liệu mà không tạo lại schema (mặc định là rebuild)")
    args = parser.parse_args()

    run_pipeline(rebuild_schema=not args.reload_only)
