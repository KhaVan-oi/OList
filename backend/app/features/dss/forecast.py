"""Lõi DSS nhập hàng. Thuần tính toán, không đụng cơ sở dữ liệu.

Mô hình dự báo trước 1 tháng (đơn giản có chủ đích, vì chuỗi chỉ ~20 tháng):
    naive  = tháng trước
    ma3    = trung bình 3 tháng gần nhất
    holt   = Holt có suy giảm xu hướng, tham số chọn bằng lưới trên chính chuỗi lịch sử
    blend  = trung bình naive và holt

Backtest: trượt theo thời gian. Mỗi bước chỉ dùng dữ liệu trước tháng cần dự báo.
Đệm nhập hàng là phân vị thực nghiệm của sai số tuyệt đối (thực tế - dự báo) trên backtest, nội suy tuyến tính,
không giả định phân phối. Theo Trapero, Cardós, Kourentzes (Omega, 2019): tồn an toàn SS = Q(CSL) của sai số dự báo
trên lead time. Ở đây lead time L = 1 tháng và mẫu chỉ ~12-14 tháng, nên đây là ước lượng thô.
"""

from __future__ import annotations

from itertools import product

import numpy as np

MODELS = ("naive", "ma3", "holt", "blend")
MIN_TRAIN = 6  # số tháng lịch sử tối thiểu trước khi dự báo bước đầu tiên
EVENT_MONTHS = ("2017-11", "2017-12")  # Black Friday 2017 và tháng sau, báo cáo kèm/không kèm

_ALPHAS = (0.2, 0.4, 0.6, 0.8, 0.95)
_BETAS = (0.05, 0.1, 0.2, 0.4)
_PHIS = (0.8, 0.9, 0.98)


def _holt_run(y, alpha, beta, phi):
    """Chạy Holt suy giảm trên y. Trả (SSE dự báo 1 bước, mức, xu hướng cuối)."""
    n = len(y)
    level = y[0]
    k = min(3, n - 1)
    trend = (y[k] - y[0]) / k if k > 0 else 0.0
    sse = 0.0
    for t in range(1, n):
        pred = level + phi * trend
        sse += (y[t] - pred) ** 2
        new_level = alpha * y[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return sse, level, trend


def holt_forecast(y) -> float:
    y = [float(v) for v in y]
    if len(y) < 3:
        return y[-1]
    best = None
    for alpha, beta, phi in product(_ALPHAS, _BETAS, _PHIS):
        sse, level, trend = _holt_run(y, alpha, beta, phi)
        if best is None or sse < best[0]:
            best = (sse, level, trend, phi)
    _, level, trend, phi = best
    return max(level + phi * trend, 0.0)


def forecast_all(history) -> dict[str, float]:
    """Dự báo tháng kế tiếp cho mọi mô hình từ một đoạn lịch sử."""
    y = [float(v) for v in history]
    naive = y[-1]
    ma3 = float(np.mean(y[-3:]))
    holt = holt_forecast(y)
    return {"naive": naive, "ma3": ma3, "holt": holt, "blend": (naive + holt) / 2}


def backtest(values) -> list[dict]:
    """Mỗi bước t (từ MIN_TRAIN) dự báo values[t] chỉ từ values[:t]."""
    rows = []
    for t in range(MIN_TRAIN, len(values)):
        rows.append({"index": t, "actual": float(values[t]), **forecast_all(values[:t])})
    return rows


def _abs_err(rows, model):
    return sum(abs(r["actual"] - r[model]) for r in rows)


def model_metrics(rows, model) -> dict:
    """WAPE, MAPE, thiên lệch trên một tập dòng backtest."""
    if not rows:
        return {"wape": None, "mape": None, "bias": None, "n": 0}
    total = sum(r["actual"] for r in rows)
    if total <= 0:
        return {"wape": None, "mape": None, "bias": None, "n": len(rows)}
    wape = _abs_err(rows, model) / total
    mape = float(np.mean([abs(r["actual"] - r[model]) / max(r["actual"], 1.0) for r in rows]))
    bias = (sum(r[model] for r in rows) - total) / total
    return {"wape": wape, "mape": mape, "bias": bias, "n": len(rows)}


MIN_ERRORS = 3  # số sai số tối thiểu để tính đệm. Ít hơn thì đệm = 0


def forecast_errors(rows, model) -> list[float]:
    """actual - forecast, cùng đơn vị với chuỗi (món hoặc R$). Dương nghĩa là cầu vượt dự báo (nguy cơ thiếu hàng)."""
    return [r["actual"] - r[model] for r in rows if r[model] > 0]


def _quantile(values, q):
    return float(np.quantile(np.asarray(values, dtype=float), q, method="linear"))


def _buffer(errors, service: float) -> float:
    """Đệm = phân vị `service` của sai số. Có thể âm khi mô hình thường dự báo cao hơn thực tế."""
    return _quantile(errors, service) if len(errors) >= MIN_ERRORS else 0.0


def order_plan(forecast: float, errors, service: float) -> dict:
    """Lượng nhập = max(dự báo + đệm, 0), đệm là phân vị `service` của sai số tuyệt đối.

    `buffer` là đệm đúng đơn vị. `buffer_pct` (= đệm / dự báo) chỉ để hiển thị.
    """
    buffer = _buffer(errors, service)
    return {
        "service": service,
        "buffer": buffer,
        "buffer_pct": buffer / forecast * 100.0 if forecast > 0 else 0.0,
        "quantity": max(forecast + buffer, 0.0),
        "n_errors": len(errors),
    }


# Các mức phục vụ mục tiêu 85/90/95/99% đúng như Trapero, Cardós, Kourentzes (Omega 84, 2019; cũng là các mức
# trong bài IJF 35, 2019 của nhóm, mục 4.3). Bài nói mức doanh nghiệp thường nhắm tới nằm trong khoảng 85-99%.
SERVICE_LEVELS = (0.85, 0.9, 0.95, 0.99)


def tradeoff(rows, model) -> list[dict]:
    """Đánh đổi thiếu hàng và dư hàng, đo bằng leave-one-out.

    Với mỗi tháng t, đệm chỉ học từ các tháng KHÁC t, rồi lượng nhập = dự báo tháng t + đệm. Vì vậy tỷ lệ
    thiếu hàng thu được là thước đo thực nghiệm, không phải cam kết lý thuyết của phân vị.
    """
    usable = [r for r in rows if r[model] > 0 and r["actual"] > 0]
    errors = [r["actual"] - r[model] for r in usable]
    out = []
    for service in SERVICE_LEVELS:
        stockouts = 0
        over = []
        short = []
        for i, r in enumerate(usable):
            others = errors[:i] + errors[i + 1:]
            qty = max(r[model] + _buffer(others, service), 0.0)
            actual = r["actual"]
            if actual > qty:
                stockouts += 1
            over.append(max(qty - actual, 0.0) / actual)
            short.append(max(actual - qty, 0.0) / actual)
        n = len(usable)
        out.append(
            {
                "service": service,
                "stockout_rate": stockouts / n if n else None,
                "overstock_pct": float(np.mean(over)) * 100 if over else None,
                "shortfall_pct": float(np.mean(short)) * 100 if short else None,
                "n": n,
            }
        )
    return out
