"""SQL tổng hợp theo năm / quý / tháng kèm tăng trưởng, dùng chung cho các route màn Thời gian.

Vì sao tăng trưởng năm và quý phải so CÙNG KỲ
--------------------------------------------
Dữ liệu delivered chỉ có 2016-09..2018-08, lại thiếu tháng 2016-11. Năm 2016 có 3 tháng, năm 2018 có 8 tháng,
quý 3/2018 có 2 tháng. Nếu lấy tổng cả kỳ chia tổng cả kỳ trước thì tỷ lệ trộn hai thứ: tăng trưởng thật và
chênh lệch số tháng. Ví dụ doanh thu hàng 2018 (T1–T8) so với 2017 (T1–T12) ra +21%, trong khi cùng kỳ T1–T8
thì tăng +141%. Quý 3/2018 so với quý 2/2018 ra khoảng −39% chỉ vì thiếu tháng 9.

Quy tắc (so sánh cùng kỳ, "like-for-like"):
    YoY năm Y = Σ_{m ∈ M} X(Y, m) / Σ_{m ∈ M} X(Y−1, m) − 1,  M = các tháng lịch có dữ liệu ở CẢ năm Y và Y−1
    QoQ quý q = như trên, ghép tháng thứ 1, 2, 3 của quý q với tháng thứ 1, 2, 3 của quý liền trước
Tổng của kỳ (product_sales, ...) vẫn là tổng đầy đủ của kỳ, không bị cắt. Mỗi dòng trả thêm:
    months_with_data   số tháng của kỳ có giao dịch delivered
    months_compared    số tháng dùng để tính tăng trưởng (|M|)
    is_partial         kỳ chưa đủ tháng lịch (năm < 12, quý < 3)

Tăng trưởng tháng (MoM) vốn đã so một tháng với một tháng, nên giữ nguyên định nghĩa; chỉ khác là tính trên
toàn chuỗi rồi mới lọc theo năm / quý, để tháng 1 vẫn so được với tháng 12 năm trước.

MoM bỏ trống khi tháng trước quá thưa
-------------------------------------
Tháng trước có giá trị nhỏ hơn THIN_MONTH_RATIO × trung vị các tháng có dữ liệu (tính riêng từng measure) thì
MoM là NULL. Ví dụ 12/2016 chỉ có 1 món, 10,90 R$: chia cho mẫu số đó ra MoM 01/2017 khoảng +1.025.573%, một con
số không mang nghĩa kinh doanh và làm trục biểu đồ giãn tới mức mọi tháng khác thành đường phẳng.

Ngưỡng 1% không nhạy: hai tháng gần như trống (09/2016 và 12/2016) chỉ bằng 0,00–0,06% trung vị, trong khi tháng thật
nhỏ nhất (10/2016) đã bằng khoảng 6,5% và 01/2017 khoảng 18%. Mọi ngưỡng trong khoảng 0,1%–6% cho cùng kết quả: chỉ
MoM của 10/2016 và 01/2017 bị bỏ trống. Không dùng 30% như quy tắc tháng đủ dữ liệu của DSS vì ngưỡng đó loại cả
01/2017, tháng thật của giai đoạn tăng trưởng, làm mất MoM 02/2017.

QoQ và YoY cùng kỳ chỉ ghép các cặp tháng mà cả hai tháng đều đạt ngưỡng trên. Riêng YoY còn cần ít nhất
MIN_YOY_MONTHS cặp tháng hợp lệ: tăng trưởng của cả năm dựa trên một hai tháng thì không còn là so sánh theo năm, mà
chỉ là tăng trưởng của vài tháng lẻ. Với dữ liệu hiện có, YoY 2017 chỉ có 1 cặp (10/2017–10/2016) nên để trống;
YoY 2018 có 8 cặp (tháng 1–8) nên vẫn là +141,13%. Ba tháng tương đương một quý, đơn vị nhỏ nhất của các so sánh
theo kỳ trên màn này.

Mọi giá trị lọc đi vào SQL bằng tham số của psycopg2, không nối chuỗi. Không dùng toán tử % trong SQL
(xung đột với placeholder), dùng mod().
"""

MEASURES = ("product_sales", "freight_value", "order_item_count")

# Tháng nhỏ hơn tỷ lệ này của trung vị các tháng là tháng thưa, không dùng làm mốc so sánh (xem docstring).
THIN_MONTH_RATIO = 0.01
# YoY chỉ tính khi có ít nhất chừng này cặp tháng hợp lệ (xem docstring).
MIN_YOY_MONTHS = 3


def thin_floor_sql(source, columns):
    """SELECT một dòng: ngưỡng tháng thưa của từng cột = THIN_MONTH_RATIO × trung vị trên `source`.

    `columns` là các cột của `source`; mỗi ngưỡng được đặt tên floor_<cột>. Hàng NULL bị percentile_cont bỏ qua.
    """
    floors = ",\n        ".join(
        f"{THIN_MONTH_RATIO} * percentile_cont(0.5) WITHIN GROUP (ORDER BY {c}) AS floor_{c}" for c in columns
    )
    return f"SELECT\n        {floors}\n    FROM {source}"

# Một dòng / tháng lịch có ít nhất một món delivered. Tháng không có giao dịch thì KHÔNG có dòng (không gán 0).
_MONTHLY_CTE = """
monthly AS (
    SELECT
        d.year, d.quarter, d.month,
        SUM(fs.price)         AS product_sales,
        SUM(fs.freight_value) AS freight_value,
        COUNT(*)              AS order_item_count
    FROM dw.fact_sales fs
    JOIN dw.dim_date d              ON fs.purchase_date_key = d.date_key
    JOIN dw.fact_customer_order fco ON fs.order_id = fco.order_id
    WHERE fco.order_status = 'delivered'
    GROUP BY d.year, d.quarter, d.month
)"""


def _sums(alias=None, prefix=""):
    col = f"{alias}." if alias else ""
    return ",\n        ".join(f"SUM({col}{m}) AS {prefix}{m}" for m in MEASURES)


def _growth(kind, min_months=None):
    """(cur − prev) / prev × 100 trên các tháng cùng kỳ. NULL khi không có tháng chung hoặc kỳ trước = 0,
    và khi có `min_months` thì NULL nếu số cặp tháng hợp lệ (s.months_compared) ít hơn mức đó."""
    def expr(m):
        pct = f"ROUND((s.cur_{m} - s.prev_{m})::numeric / NULLIF(s.prev_{m}, 0) * 100, 2)"
        if min_months:
            pct = f"CASE WHEN COALESCE(s.months_compared, 0) < {min_months} THEN NULL ELSE {pct} END"
        return f"{pct} AS {kind}_{m}_pct"

    return ",\n    ".join(expr(m) for m in MEASURES)


def _rounded(alias="p"):
    return (
        f"ROUND({alias}.product_sales, 2) AS product_sales,\n"
        f"    ROUND({alias}.freight_value, 2) AS freight_value,\n"
        f"    {alias}.order_item_count::bigint AS order_item_count"
    )


def year_sql(year=None):
    """Tổng theo năm + YoY cùng kỳ. Trả (sql, params).

    Chỉ ghép các cặp tháng mà cả hai tháng đều đạt ngưỡng tháng thưa; YoY là NULL khi số cặp hợp lệ
    (months_compared) nhỏ hơn MIN_YOY_MONTHS.
    """
    where = "WHERE p.year = %s" if year is not None else ""
    sql = f"""
WITH {_MONTHLY_CTE},
floors AS (
    {thin_floor_sql("monthly", MEASURES)}
),
period AS (
    SELECT year,
        {_sums()},
        COUNT(*) AS months_with_data
    FROM monthly
    GROUP BY year
),
same_period AS (
    SELECT cur.year,
        {_comparable_sums("cur")},
        {_comparable_sums("prev")},
        COUNT(*) FILTER (WHERE {_both_above_floor()}) AS months_compared
    FROM monthly cur
    JOIN monthly prev ON prev.year = cur.year - 1 AND prev.month = cur.month
    CROSS JOIN floors f
    GROUP BY cur.year
)
SELECT
    p.year,
    {_rounded()},
    {_growth("yoy", min_months=MIN_YOY_MONTHS)},
    p.months_with_data,
    COALESCE(s.months_compared, 0) AS months_compared,
    p.months_with_data < 12        AS is_partial
FROM period p
LEFT JOIN same_period s ON s.year = p.year
{where}
ORDER BY p.year
"""
    return sql, ((year,) if year is not None else ())


def _comparable_sums(side):
    """SUM của `side` (cur | prev) chỉ trên các cặp tháng mà cả hai tháng đều đạt ngưỡng tháng thưa của measure đó."""
    return ",\n        ".join(
        f"SUM(CASE WHEN cur.{m} >= f.floor_{m} AND prev.{m} >= f.floor_{m} THEN {side}.{m} END) AS {side}_{m}"
        for m in MEASURES
    )


def _both_above_floor():
    """Điều kiện một cặp tháng hợp lệ: cả hai tháng đạt ngưỡng tháng thưa ở cả ba measure."""
    return " AND ".join(f"cur.{m} >= f.floor_{m} AND prev.{m} >= f.floor_{m}" for m in MEASURES)


def quarter_sql(year=None):
    """Tổng theo quý + QoQ cùng kỳ (tháng thứ k của quý so với tháng thứ k của quý trước). Trả (sql, params).

    Một cặp tháng chỉ được đem so khi cả hai tháng đều đạt THIN_MONTH_RATIO × trung vị (cùng ngưỡng với MoM).
    Ví dụ Q1/2017 so với Q4/2016: cặp 03/2017–12/2016 bị loại vì 12/2016 chỉ có 10,90 R$, chỉ còn cặp
    01/2017–10/2016. Quý trước không còn cặp nào thì QoQ là NULL. months_compared đếm các cặp đạt ở cả ba measure.
    """
    where = "WHERE p.year = %s" if year is not None else ""
    sql = f"""
WITH {_MONTHLY_CTE},
floors AS (
    {thin_floor_sql("monthly", MEASURES)}
),
period AS (
    SELECT year, quarter,
        {_sums()},
        COUNT(*) AS months_with_data
    FROM monthly
    GROUP BY year, quarter
),
same_period AS (
    SELECT cur.year, cur.quarter,
        {_comparable_sums("cur")},
        {_comparable_sums("prev")},
        COUNT(*) FILTER (WHERE {_both_above_floor()}) AS months_compared
    FROM monthly cur
    JOIN monthly prev
      ON prev.year * 4 + prev.quarter = cur.year * 4 + cur.quarter - 1
     AND mod(prev.month - 1, 3) = mod(cur.month - 1, 3)
    CROSS JOIN floors f
    GROUP BY cur.year, cur.quarter
)
SELECT
    p.year, p.quarter,
    {_rounded()},
    {_growth("qoq")},
    p.months_with_data,
    COALESCE(s.months_compared, 0) AS months_compared,
    p.months_with_data < 3         AS is_partial
FROM period p
LEFT JOIN same_period s ON s.year = p.year AND s.quarter = p.quarter
{where}
ORDER BY p.year, p.quarter
"""
    return sql, ((year,) if year is not None else ())


def _mom(m):
    """MoM của measure m; NULL khi tháng trước thiếu, bằng 0 hoặc dưới ngưỡng tháng thưa (cột floor_m của CTE floors)."""
    prev = f"LAG({m}) OVER (ORDER BY year, month)"
    return (
        f"CASE WHEN {prev} < floor_{m} THEN NULL "
        f"ELSE ROUND(({m} - {prev})::numeric / NULLIF({prev}, 0) * 100, 2) END AS mom_{m}_pct"
    )


def month_sql(year=None, quarter=None):
    """Chuỗi tháng liên tục (tháng không có giao dịch để NULL) + MoM + YTD. Trả (sql, params).

    Chuỗi trải từ tháng delivered đầu tiên đến tháng delivered cuối cùng. LAG chạy trên cả chuỗi rồi mới lọc,
    nên tháng 1 của năm đang xem vẫn có MoM so với tháng 12 năm trước. Tháng trước NULL hoặc quá thưa
    (dưới THIN_MONTH_RATIO × trung vị) thì MoM là NULL.
    """
    filters, params = [], []
    if year is not None:
        filters.append("year = %s")
        params.append(year)
    if quarter is not None:
        filters.append("quarter = %s")
        params.append(quarter)
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    moms = ",\n        ".join(_mom(m) for m in MEASURES)
    ytds = ",\n        ".join(f"SUM({m}) OVER (PARTITION BY year ORDER BY month) AS ytd_{m}" for m in MEASURES)
    sql = f"""
WITH {_MONTHLY_CTE},
series AS (
    SELECT gs::date AS month_start
    FROM generate_series(
        (SELECT make_date(min(year * 100 + month) / 100, mod(min(year * 100 + month), 100), 1) FROM monthly),
        (SELECT make_date(max(year * 100 + month) / 100, mod(max(year * 100 + month), 100), 1) FROM monthly),
        INTERVAL '1 month'
    ) AS gs
),
base AS (
    SELECT
        EXTRACT(YEAR FROM s.month_start)::int    AS year,
        EXTRACT(QUARTER FROM s.month_start)::int AS quarter,
        EXTRACT(MONTH FROM s.month_start)::int   AS month,
        m.product_sales, m.freight_value, m.order_item_count
    FROM series s
    LEFT JOIN monthly m
      ON m.year = EXTRACT(YEAR FROM s.month_start) AND m.month = EXTRACT(MONTH FROM s.month_start)
),
floors AS (
    {thin_floor_sql("monthly", MEASURES)}
),
metrics AS (
    SELECT year, quarter, month, product_sales, freight_value, order_item_count,
        {moms},
        {ytds}
    FROM base CROSS JOIN floors
)
SELECT
    year, month,
    ROUND(product_sales, 2) AS product_sales,
    ROUND(freight_value, 2) AS freight_value,
    order_item_count,
    mom_product_sales_pct, mom_freight_value_pct, mom_order_item_count_pct,
    ROUND(ytd_product_sales, 2) AS ytd_product_sales,
    ROUND(ytd_freight_value, 2) AS ytd_freight_value,
    ytd_order_item_count::bigint AS ytd_order_item_count
FROM metrics
{where}
ORDER BY year, month
"""
    return sql, tuple(params)
