"""Tạo view DSS dw.v_dss_monthly_demand và đối soát với OLAP."""
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db_connect import get_connection

SQL_PATH = Path(__file__).resolve().parent / "sql" / "dss" / "01_demand_mart.sql"


def main() -> None:
    conn = get_connection()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SQL_PATH.read_text(encoding="utf-8"))
        print("[+] Đã tạo/cập nhật view dw.v_dss_monthly_demand")

        cur.execute("SELECT round(sum(revenue), 2), sum(units) FROM dw.v_dss_monthly_demand")
        view_revenue, view_units = cur.fetchone()
        cur.execute(
            """
            SELECT round(sum(s.price), 2), count(*)
            FROM dw.fact_sales s
            JOIN dw.fact_customer_order o ON o.order_id = s.order_id
            WHERE o.order_status = 'delivered'
            """
        )
        fact_revenue, fact_units = cur.fetchone()
        ok = view_revenue == fact_revenue and view_units == fact_units
        print(f"    view : {view_revenue} R$, {view_units} món")
        print(f"    fact : {fact_revenue} R$, {fact_units} món")
        print("[PASS] Đối soát view = fact_sales delivered" if ok else "[FAIL] View lệch fact_sales")

        cur.execute(
            """
            SELECT month_start, sum(units), round(sum(revenue), 0)
            FROM dw.v_dss_monthly_demand
            GROUP BY month_start ORDER BY month_start
            """
        )
        print("\nTháng | món | doanh thu")
        for month, units, revenue in cur.fetchall():
            print(f"{month} | {units:>6} | {revenue:>10}")
    conn.close()
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
