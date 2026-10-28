"""Chạy sql/olap/02_product_seller_geo.sql và in từng bảng kết quả."""
import re
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db_connect import get_connection

SQL_PATH = Path(__file__).resolve().parent / "sql" / "olap" / "02_product_seller_geo.sql"

SECTION_TITLES = {
    0: "0) Tổng nền valid_sales",
    1: "1) Top 10 danh mục",
    2: "2) Top 10 seller",
    3: "3) Pareto 20% product_id",
    4: "4) Tỷ lệ cước / giá",
    5: "5) Đơn & doanh thu theo bang",
    6: "6) ROLL-UP state/city",
    7: "7) DRILL-DOWN bang #1 → danh mục",
    8: "8) SLICE danh mục #1",
    9: "9) DICE top10 seller ∩ SP/RJ/MG ∩ health_beauty",
    10: "10) PIVOT top5 danh mục × 5 bang",
    11: "11) Top 3 danh mục mỗi bang",
}


def split_statements(sql_text: str) -> list[str]:
    """Tách câu lệnh; bỏ comment dòng và khối trống."""
    lines = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    parts = re.split(r";\s*\n", cleaned)
    stmts = []
    for part in parts:
        s = part.strip().rstrip(";").strip()
        if s:
            stmts.append(s)
    return stmts


def main() -> None:
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    stmts = split_statements(sql_text)

    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    select_idx = 0
    try:
        for stmt in stmts:
            cur.execute(stmt)
            if cur.description is None:
                print(f"[OK] {stmt.split()[0].upper()} ...")
                continue

            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            title = SECTION_TITLES.get(select_idx, f"SELECT #{select_idx}")
            select_idx += 1

            print("\n" + "=" * 72)
            print(title)
            print("=" * 72)
            print(" | ".join(cols))
            print("-" * 72)
            for row in rows[:40]:
                print(" | ".join("" if v is None else str(v) for v in row))
            if len(rows) > 40:
                print(f"... ({len(rows) - 40} dòng nữa, tổng {len(rows)})")
            else:
                print(f"({len(rows)} dòng)")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
