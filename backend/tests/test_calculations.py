"""Test phần tính toán thuần (không cần database).

Chạy từ thư mục gốc dự án:
    python -m unittest discover -s backend/tests -t backend
"""

import re
import unittest

import numpy as np

from app.features.dss import forecast as fc
from app.features.sales_time import growth


class NaiveScaleTest(unittest.TestCase):
    def test_mean_absolute_first_difference(self):
        # |3-1| = 2, |6-3| = 3 -> trung bình 2,5
        self.assertAlmostEqual(fc.naive_scale([1, 3, 6]), 2.5)

    def test_flat_or_short_series_has_no_scale(self):
        self.assertIsNone(fc.naive_scale([5, 5, 5]))
        self.assertIsNone(fc.naive_scale([5]))


class BacktestTest(unittest.TestCase):
    def setUp(self):
        self.values = [100, 110, 105, 120, 130, 125, 140, 150, 145, 160]

    def test_starts_at_min_train(self):
        rows = fc.backtest(self.values)
        self.assertEqual(rows[0]["index"], fc.MIN_TRAIN)
        self.assertEqual(len(rows), len(self.values) - fc.MIN_TRAIN)

    def test_no_look_ahead(self):
        """Đổi các giá trị SAU tháng t không được làm đổi dự báo hay mẫu số MASE của tháng t."""
        base = fc.backtest(self.values)
        changed = self.values[:7] + [9999, 9999, 9999]
        other = fc.backtest(changed)
        first = base[0]  # t = MIN_TRAIN = 6, chỉ dùng values[:6]
        self.assertEqual(first["index"], 6)
        for key in (*fc.MODELS, "scale"):
            self.assertAlmostEqual(first[key], other[0][key])

    def test_scale_uses_history_only(self):
        rows = fc.backtest(self.values)
        t = rows[0]["index"]
        self.assertAlmostEqual(rows[0]["scale"], fc.naive_scale(self.values[:t]))


class MetricsTest(unittest.TestCase):
    rows = [
        {"actual": 100.0, "naive": 90.0, "scale": 10.0},
        {"actual": 200.0, "naive": 220.0, "scale": 20.0},
    ]

    def test_wape(self):
        # (10 + 20) / (100 + 200)
        self.assertAlmostEqual(fc.model_metrics(self.rows, "naive")["wape"], 0.1)

    def test_mase(self):
        # mean(10/10, 20/20) = 1
        self.assertAlmostEqual(fc.mase(self.rows, "naive"), 1.0)

    def test_mase_skips_rows_without_scale(self):
        rows = self.rows + [{"actual": 50.0, "naive": 0.0, "scale": None}]
        self.assertAlmostEqual(fc.mase(rows, "naive"), 1.0)

    def test_bias_sign(self):
        # dự báo tổng 310, thực tế 300 -> lệch cao +1/30
        self.assertAlmostEqual(fc.model_metrics(self.rows, "naive")["bias"], 10 / 300)


class OrderPlanTest(unittest.TestCase):
    def test_buffer_is_linear_quantile_of_errors(self):
        errors = [-10.0, 0.0, 10.0, 20.0]
        plan = fc.order_plan(100.0, errors, 0.9)
        expected = float(np.quantile(errors, 0.9, method="linear"))  # 17
        self.assertAlmostEqual(plan["buffer"], expected)
        self.assertAlmostEqual(plan["quantity"], 100.0 + expected)

    def test_too_few_errors_gives_zero_buffer(self):
        plan = fc.order_plan(100.0, [5.0, 6.0], 0.9)
        self.assertEqual(plan["buffer"], 0.0)
        self.assertEqual(plan["quantity"], 100.0)

    def test_quantity_never_negative(self):
        plan = fc.order_plan(10.0, [-50.0, -40.0, -30.0], 0.85)
        self.assertEqual(plan["quantity"], 0.0)


class GrowthSqlTest(unittest.TestCase):
    """SQL đi qua psycopg2 nên mọi '%' không phải placeholder sẽ làm hỏng câu lệnh (lỗi đã gặp khi viết)."""

    def _assert_only_placeholders(self, sql, params):
        stray = re.findall(r"%(?!s)", sql)
        self.assertEqual(stray, [], "dùng mod() thay cho toán tử %")
        self.assertEqual(sql.count("%s"), len(params))

    def test_year(self):
        self._assert_only_placeholders(*growth.year_sql())
        self._assert_only_placeholders(*growth.year_sql(2018))

    def test_quarter(self):
        self._assert_only_placeholders(*growth.quarter_sql())
        self._assert_only_placeholders(*growth.quarter_sql(2017))

    def test_month(self):
        self._assert_only_placeholders(*growth.month_sql())
        self._assert_only_placeholders(*growth.month_sql(2017, 3))

    def test_mom_skips_thin_previous_month(self):
        month_sql, _ = growth.month_sql()
        for m in growth.MEASURES:
            self.assertIn(f"LAG({m}) OVER (ORDER BY year, month) < floor_{m} THEN NULL", month_sql)
        floors = growth.thin_floor_sql("monthly", growth.MEASURES)
        self.assertIn(f"{growth.THIN_MONTH_RATIO} * percentile_cont(0.5)", floors)
        self.assertIn("AS floor_order_item_count", floors)

    def test_qoq_skips_thin_month_pairs(self):
        quarter_sql, _ = growth.quarter_sql()
        for m in growth.MEASURES:
            self.assertIn(
                f"SUM(CASE WHEN cur.{m} >= f.floor_{m} AND prev.{m} >= f.floor_{m} THEN prev.{m} END) AS prev_{m}",
                quarter_sql,
            )
        self.assertIn("CROSS JOIN floors f", quarter_sql)

    def test_yoy_needs_min_valid_months(self):
        year_sql, _ = growth.year_sql()
        self.assertIn("CROSS JOIN floors f", year_sql)
        self.assertIn(f"WHEN COALESCE(s.months_compared, 0) < {growth.MIN_YOY_MONTHS} THEN NULL", year_sql)
        quarter_sql, _ = growth.quarter_sql()
        self.assertNotIn("COALESCE(s.months_compared, 0) <", quarter_sql)  # QoQ không có điều kiện số tháng

    def test_like_for_like_join_conditions(self):
        year_sql, _ = growth.year_sql()
        self.assertIn("prev.year = cur.year - 1 AND prev.month = cur.month", year_sql)
        quarter_sql, _ = growth.quarter_sql()
        self.assertIn("mod(prev.month - 1, 3) = mod(cur.month - 1, 3)", quarter_sql)


if __name__ == "__main__":
    unittest.main()
