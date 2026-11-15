"""Độ nhạy của MIN_TRAIN (số tháng lịch sử tối thiểu trước khi dự báo bước đầu tiên).

MIN_TRAIN do nhóm tự đặt (=6), không có paper quy định. Script này đổi MIN_TRAIN từ 3 đến 10 và xem kết quả đổi ra sao.

Điều cần hiểu: dự báo tại tháng t luôn dùng TOÀN BỘ lịch sử trước t, nên MIN_TRAIN KHÔNG đổi giá trị dự báo của một
tháng. Nó chỉ quyết định tháng nào được đưa vào backtest (các tháng đầu, ít lịch sử, có được tính hay không).
Vì vậy "độ nhạy" thực chất là độ nhạy với việc chọn tập tháng kiểm tra. Ba bảng:
  A. WAPE theo từng MIN_TRAIN (tập tháng kiểm tra khác nhau, nên đọc kèm n_test).
  B. Sai số từng tháng đầu, cho thấy vì sao A đổi.
  C. Hệ quả lên đệm, lượng nhập và tỷ lệ thiếu hàng.

Chạy: python docs/dss_exploration/07_min_train_sensitivity.py  (cần kho đã có view dw.v_dss_monthly_demand)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.features.dss import forecast as fc  # noqa: E402
from db_connect import get_connection  # noqa: E402

START, END = "2017-01", "2018-08"
KS = range(3, 11)
SERVICE = 0.9


def months():
    y, m = 2017, 1
    out = []
    while (y, m) <= (2018, 8):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def load(cur, column=None, top=None):
    """Trả danh sách chuỗi units theo tháng: tổng, hoặc top-N theo bang/danh mục."""
    ms = months()
    if column is None:
        cur.execute(
            "SELECT to_char(month_start,'YYYY-MM'), sum(units) FROM dw.v_dss_monthly_demand "
            "WHERE month_start >= %s AND month_start <= %s GROUP BY 1",
            (START + "-01", END + "-01"),
        )
        d = {r[0]: float(r[1]) for r in cur.fetchall()}
        return [[d.get(x, 0.0) for x in ms]]
    cur.execute(
        f"""WITH top AS (SELECT {column} k FROM dw.v_dss_monthly_demand
                         WHERE month_start >= %s AND month_start <= %s AND {column} IS NOT NULL
                         GROUP BY 1 ORDER BY sum(revenue) DESC LIMIT %s)
            SELECT v.{column}, to_char(v.month_start,'YYYY-MM'), sum(v.units)
            FROM dw.v_dss_monthly_demand v JOIN top ON top.k = v.{column}
            WHERE v.month_start >= %s AND v.month_start <= %s GROUP BY 1, 2""",
        (START + "-01", END + "-01", top, START + "-01", END + "-01"),
    )
    by = {}
    for k, mo, u in cur.fetchall():
        by.setdefault(k, {})[mo] = float(u)
    return [[d.get(x, 0.0) for x in ms] for d in by.values()]


def pooled_wape(series_list, k, model):
    fc.MIN_TRAIN = k
    err = tot = 0.0
    for values in series_list:
        for r in fc.backtest(values):
            err += abs(r["actual"] - r[model])
            tot += r["actual"]
    return err / tot if tot else float("nan"), len(series_list[0]) - k


def main():
    conn = get_connection()
    cur = conn.cursor()
    total = load(cur)
    states = load(cur, "customer_state", 10)
    cats = load(cur, "category", 15)
    conn.close()
    n_total = len(total[0])

    print(f"Chuỗi {n_total} tháng ({START} → {END}). MIN_TRAIN thử: {min(KS)}..{max(KS)}. Mặc định hiện tại: 6.\n")

    print("A. WAPE theo MIN_TRAIN (tập tháng kiểm tra khác nhau, đọc kèm n_test)")
    print("MIN_TRAIN | n_test | WAPE blend tổng | naive tổng | blend 10 bang | blend 15 danh mục")
    for k in KS:
        wb, n = pooled_wape(total, k, "blend")
        wn, _ = pooled_wape(total, k, "naive")
        ws, _ = pooled_wape(states, k, "blend")
        wc, _ = pooled_wape(cats, k, "blend")
        print(f"{k:>9} | {n:>6} | {wb*100:>14.1f}% | {wn*100:>9.1f}% | {ws*100:>12.1f}% | {wc*100:>16.1f}%")

    print("\nB. Sai số từng tháng đầu của blend (toàn kho). Đây là các tháng vào hoặc ra backtest khi MIN_TRAIN đổi")
    print("chỉ số | tháng   | lịch sử có | thực tế | blend | |sai số| %")
    fc.MIN_TRAIN = min(KS)
    ms = months()
    for r in fc.backtest(total[0]):
        if r["index"] <= max(KS):
            pct = abs(r["actual"] - r["blend"]) / r["actual"] * 100
            print(f"{r['index']:>6} | {ms[r['index']]} | {r['index']:>10} | {r['actual']:>7.0f} | {r['blend']:>5.0f} | {pct:>9.1f}%")

    print(f"\nC. Hệ quả cho quyết định nhập hàng (toàn kho, phân vị {int(SERVICE*100)}%, đã bỏ Black Friday khỏi mẫu sai số)")
    print("MIN_TRAIN | n sai số | đệm (món) | đệm % | lượng nhập | thiếu hàng LOO")
    for k in KS:
        fc.MIN_TRAIN = k
        values = total[0]
        ms = months()
        rows = [{**r, "month": ms[r["index"]]} for r in fc.backtest(values)]
        rows = [r for r in rows if r["month"] not in fc.EVENT_MONTHS]
        nxt = fc.forecast_all(values)["blend"]
        errs = fc.forecast_errors(rows, "blend")
        plan = fc.order_plan(nxt, errs, SERVICE)
        t = [x for x in fc.tradeoff(rows, "blend") if x["service"] == SERVICE][0]
        so = t["stockout_rate"]
        so_txt = "n/a" if so is None else f"{so*100:.1f}%"
        print(
            f"{k:>9} | {plan['n_errors']:>8} | {plan['buffer']:>9.0f} | {plan['buffer_pct']:>4.1f}% | {plan['quantity']:>10.0f} | {so_txt:>13}"
        )
    fc.MIN_TRAIN = 6


if __name__ == "__main__":
    main()
