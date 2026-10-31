"""Chạy sql/olap/02_product_seller_geo.sql và in từng luồng."""
import re
import sys
import time
from decimal import Decimal
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
    7: "7a) DRILL-DOWN nấc 1 — toàn bộ",
    8: "7b) DRILL-DOWN nấc 2 — các bang",
    9: "7c) DRILL-DOWN nấc 3 — thành phố mọi bang",
    10: "8) SLICE theo olap_slice_category",
    11: "9) DICE seller ∩ olap_dice_state ∩ olap_dice_category",
    12: "10) PIVOT top5 danh mục × 5 bang",
    13: "11) Top 3 danh mục mỗi bang",
}

# Bảng dài hơn mức này chỉ in vài dòng đại diện. 81 dòng top-3 vẫn in đủ.
FULL_ROW_LIMIT = 90


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


def execute_statements(cur, stmts: list[str]) -> list[dict]:
    """Chạy lần lượt. SELECT trả cols/rows; DDL để rows = None."""
    results = []
    for stmt in stmts:
        t0 = time.perf_counter()
        cur.execute(stmt)
        ms = (time.perf_counter() - t0) * 1000
        if cur.description is None:
            results.append({"sql": stmt, "cols": None, "rows": None, "ms": ms})
            continue
        results.append(
            {
                "sql": stmt,
                "cols": [d[0] for d in cur.description],
                "rows": cur.fetchall(),
                "ms": ms,
            }
        )
    return results


def _money(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _print_rows(cols: list[str], rows: list) -> None:
    print(" | ".join(cols), flush=True)
    print("-" * 72, flush=True)
    for row in rows:
        print(" | ".join(_cell(v) for v in row), flush=True)


def _ddl_label(stmt: str) -> str | None:
    upper = stmt.lstrip().upper()
    if upper.startswith("CREATE") and " VIEW " in f" {upper[:80]} ":
        return "valid_sales"
    if "INSERT INTO olap_dice_seller" in stmt:
        return "tham số slice / dice"
    return None


def _print_select(index: int, item: dict) -> None:
    cols = item["cols"]
    rows = item["rows"]
    title = SECTION_TITLES.get(index, f"SELECT #{index}")
    print("\n" + "=" * 72, flush=True)
    print(f"{title}  ({item['ms']:.0f} ms, {len(rows)} dòng)", flush=True)
    print("=" * 72, flush=True)

    if index == 6:
        by_name = [dict(zip(cols, row)) for row in rows]
        picked = []
        for rec in by_name:
            if rec["customer_state"] == "(ALL STATES)":
                picked.append(rec)
                break
        for rec in by_name:
            if rec["grouping_state"] == 0 and rec["grouping_city"] == 1:
                picked.append(rec)
                break
        for rec in by_name:
            if rec["grouping_state"] == 0 and rec["grouping_city"] == 0:
                picked.append(rec)
                break
        _print_rows(cols, [[rec[c] for c in cols] for rec in picked])
        print(
            f"... tổng {len(rows)} dòng (1 tổng kho + tổng từng bang + từng thành phố)",
            flush=True,
        )
        return

    if len(rows) <= FULL_ROW_LIMIT:
        _print_rows(cols, rows)
        return

    _print_rows(cols, rows[:3])
    revenue_sum = None
    if "revenue" in cols:
        rev_i = cols.index("revenue")
        revenue_sum = sum((_money(row[rev_i]) for row in rows), Decimal("0"))
    extra = f", cộng revenue = {revenue_sum}" if revenue_sum is not None else ""
    print(f"... tổng {len(rows)} dòng{extra}; chỉ in 3 dòng đầu", flush=True)


def _flow_lines(selects: list[dict]) -> list[tuple[bool, str]]:
    base = dict(zip(selects[0]["cols"], selects[0]["rows"][0]))
    total = _money(base["total_revenue"])
    orders = int(base["orders_with_items"])
    items = int(base["items_sold"])

    roll_cols = selects[6]["cols"]
    roll_all = next(
        dict(zip(roll_cols, row))
        for row in selects[6]["rows"]
        if dict(zip(roll_cols, row))["customer_state"] == "(ALL STATES)"
    )
    drill = dict(zip(selects[7]["cols"], selects[7]["rows"][0]))
    state_rows = selects[5]["rows"]
    state_rev_i = selects[5]["cols"].index("revenue")
    state_ord_i = selects[5]["cols"].index("orders")
    sum_state_rev = sum((_money(row[state_rev_i]) for row in state_rows), Decimal("0"))
    sum_state_orders = sum(int(row[state_ord_i]) for row in state_rows)
    city_rev_i = selects[9]["cols"].index("revenue")
    sum_city_rev = sum((_money(row[city_rev_i]) for row in selects[9]["rows"]), Decimal("0"))

    same_total = (
        _money(roll_all["revenue"]) == total
        and _money(drill["revenue"]) == total
        and sum_state_rev == total
        and sum_city_rev == total
        and int(roll_all["orders"]) == orders
        and int(drill["orders"]) == orders
        and sum_state_orders == orders
        and int(roll_all["items_sold"]) == items
        and int(drill["items_sold"]) == items
    )
    lines = [
        (
            same_total,
            f"nền = roll-up = drill = cộng bang = cộng thành phố | "
            f"revenue={total} | orders={orders} | items={items}",
        )
    ]

    top_cat = selects[1]["rows"][0][0]
    slice_cats = {row[0] for row in selects[10]["rows"]}
    lines.append(
        (
            top_cat == "health_beauty" and slice_cats == {"health_beauty"},
            f"top 1 và slice = {top_cat} | slice {len(selects[10]['rows'])} bang",
        )
    )

    top_sellers = {str(row[0]).strip() for row in selects[2]["rows"]}
    dice_rows = selects[11]["rows"]
    dice_sellers = {str(row[0]).strip() for row in dice_rows}
    dice_states = {str(row[1]).strip() for row in dice_rows}
    dice_cats = {row[2] for row in dice_rows}
    lines.append(
        (
            len(top_sellers) == 10
            and dice_sellers <= top_sellers
            and dice_states <= {"SP", "RJ", "MG"}
            and dice_cats <= {"health_beauty"}
            and len(dice_rows) >= 1,
            f"dice {len(dice_rows)} dòng, {len(dice_sellers)}/10 seller, "
            f"bang={sorted(dice_states)}, danh mục={sorted(dice_cats)}",
        )
    )

    pivot_rows = selects[12]["rows"]
    pivot_ok = len(pivot_rows) == 5
    for row in pivot_rows:
        parts = sum((_money(v) for v in row[1:6]), Decimal("0"))
        pivot_ok = pivot_ok and parts == _money(row[6])
    top5 = [row[0] for row in selects[1]["rows"][:5]]
    pivot_cats = [row[0] for row in pivot_rows]
    lines.append(
        (
            pivot_ok and set(pivot_cats) == set(top5),
            f"pivot 5 danh mục, mỗi hàng cộng đủ 5 cột | thứ tự 5 bang: {pivot_cats}",
        )
    )
    if pivot_cats != top5:
        lines.append(
            (
                True,
                f"hạng toàn kho: {top5} | pivot xếp theo tổng 5 bang: {pivot_cats}",
            )
        )

    per_state: dict[str, int] = {}
    ranks_ok = True
    for row in selects[13]["rows"]:
        per_state[row[0]] = per_state.get(row[0], 0) + 1
        if int(row[5]) > 3:
            ranks_ok = False
    lines.append(
        (
            ranks_ok and len(per_state) == len(state_rows) and all(n <= 3 for n in per_state.values()),
            f"top 3 mỗi bang: {len(per_state)} bang, mỗi bang ≤ 3 dòng",
        )
    )
    return lines


def main() -> int:
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    stmts = split_statements(sql_text)

    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        results = execute_statements(cur, stmts)
    finally:
        cur.close()
        conn.close()

    select_idx = 0
    selects = []
    for item in results:
        if item["rows"] is None:
            label = _ddl_label(item["sql"])
            if label:
                print(f"[OK] {label}  ({item['ms']:.0f} ms)", flush=True)
            continue
        _print_select(select_idx, item)
        selects.append(item)
        select_idx += 1

    print("\n" + "=" * 72, flush=True)
    print("Đối chiếu các luồng", flush=True)
    print("=" * 72, flush=True)
    checks = _flow_lines(selects)
    failed = 0
    for ok, detail in checks:
        if not ok:
            failed += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {detail}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
