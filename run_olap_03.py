"""Chạy sql/olap/03_customer_payment.sql và in từng bảng kết quả."""
import re
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db_connect import get_connection

SQL_PATH = Path(__file__).resolve().parent / "sql" / "olap" / "03_customer_payment.sql"

SECTION_TITLES = {
    0: "0) Tổng nền valid_customer_orders (Khách, Đơn, Monetary & AOV delivered)",
    1: "1) KPI Tỷ lệ khách hàng quay lại mua (Repeat Customer Rate) & ARPU",
    2: "2) KPI Tỷ lệ hủy đơn / giao thành công theo trạng thái order_status",
    3: "3) KPI Số khách, số đơn, tổng thanh toán và AOV theo bang",
    4: "4a) ROLL-UP (Chiều Khách hàng): Bậc tần suất -> Nhóm khách -> Toàn bộ",
    5: "4b) ROLL-UP (Trạng thái đơn): (Trạng thái, Bang) -> Trạng thái -> Toàn bộ",
    6: "5) CUBE (Đơn delivered): 5 Bang lớn (SP, RJ, MG, RS, PR) × Năm",
    7: "6a) DRILL-DOWN (Chiều Khách hàng): Toàn bộ -> Nhóm khách -> Bậc tần suất",
    8: "6b) DRILL-DOWN (Chiều Địa lý): Toàn quốc -> Bang SP -> Top thành phố tại SP",
    9: "7a) SLICE (spending_tier = 'VIP'): Top 20 khách hàng VIP (> 1.000 R$)",
    10: "7b) SLICE (spending_tier = 'VIP'): Thống kê khách hàng VIP theo bang",
    11: "8a) DICE (Sub-cube): SP/RJ/MG × Năm 2017–2018 × Repeat Buyer (>= 2 đơn)",
    12: "8b) DICE (Chi tiết Top 20 khách): Bang SP ∩ 2017–2018 ∩ Số đơn >= 2",
    13: "9a) PIVOT: Ma trận 27 Bang × 8 Trạng thái đơn & Thanh toán delivered",
    14: "9b) PIVOT: Ma trận 5 Bang cố định × 3 Năm (2016..2018) & Quy mô đơn",
    15: "10) TRUY VẤN NÂNG CAO (Window Function): Top 3 khách chi tiêu theo bang & Percentile",
}


def split_statements(sql_text: str) -> list[str]:
    """Tách câu lệnh; bỏ comment dòng và khối trống."""
    lines = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    parts = re.split(r";\s*(?:\n|$)", cleaned)
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

            print("\n" + "=" * 78)
            print(title)
            print("=" * 78)
            print(" | ".join(cols))
            print("-" * 78)
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

