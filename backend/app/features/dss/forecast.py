"""Lõi DSS nhập hàng và khuyến mãi. Thuần tính toán, không đụng cơ sở dữ liệu.

Mô hình dự báo trước 1 tháng (đơn giản có chủ đích, vì chuỗi chỉ ~20 tháng):
    naive  = tháng trước
    ma3    = trung bình 3 tháng gần nhất
    holt   = Holt có suy giảm xu hướng, tham số chọn bằng lưới trên chính chuỗi lịch sử
    blend  = trung bình naive và holt

Backtest: trượt theo thời gian. Mỗi bước chỉ dùng dữ liệu trước tháng cần dự báo.
Khoảng đệm nhập hàng lấy từ sai số tương đối thực nghiệm của backtest, không giả định phân phối.
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


def pick_model(rows) -> str:
    """Mô hình có WAPE thấp nhất trên backtest. Lưu ý: chọn và đo trên cùng cửa sổ, nên hơi lạc quan."""
    scored = [(model_metrics(rows, m)["wape"], m) for m in MODELS]
    scored = [(w, m) for w, m in scored if w is not None]
    if not scored:
        return "naive"
    return min(scored)[1]


def relative_errors(rows, model) -> list[float]:
    """actual / forecast - 1. Dương nghĩa là cầu vượt dự báo (nguy cơ thiếu hàng)."""
    return [r["actual"] / r[model] - 1.0 for r in rows if r[model] > 0]


def _quantile(values, q):
    return float(np.quantile(np.asarray(values, dtype=float), q, method="higher"))


def order_plan(forecast: float, errors, service: float) -> dict:
    """Lượng nhập = dự báo × (1 + phân vị `service` của sai số tương đối)."""
    if len(errors) < 3:
        multiplier = 1.0
    else:
        multiplier = max(1.0 + _quantile(errors, service), 0.0)
    return {
        "service": service,
        "multiplier": multiplier,
        "quantity": forecast * multiplier,
        "buffer_pct": (multiplier - 1.0) * 100.0,
    }


SERVICE_LEVELS = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)


def tradeoff(rows, model) -> list[dict]:
    """Đánh đổi thiếu hàng và dư hàng, đo bằng leave-one-out.

    Với mỗi tháng t, hệ số đệm chỉ học từ các tháng KHÁC t. Vì vậy tỷ lệ thiếu hàng thu được
    là thước đo thực nghiệm, không phải cam kết lý thuyết của phân vị.
    """
    usable = [r for r in rows if r[model] > 0 and r["actual"] > 0]
    errors = [r["actual"] / r[model] - 1.0 for r in usable]
    out = []
    for service in SERVICE_LEVELS:
        stockouts = 0
        over = []
        short = []
        for i, r in enumerate(usable):
            others = errors[:i] + errors[i + 1:]
            multiplier = max(1.0 + _quantile(others, service), 0.0) if len(others) >= 3 else 1.0
            qty = r[model] * multiplier
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


def event_uplift(months, values, event="2017-11", base=("2017-09", "2017-10")):
    """Mức tăng của tháng sự kiện so với trung bình hai tháng liền trước. Chỉ là tham chiếu quan sát."""
    idx = {m: i for i, m in enumerate(months)}
    if event not in idx or any(b not in idx for b in base):
        return None
    base_avg = float(np.mean([values[idx[b]] for b in base]))
    if base_avg <= 0:
        return None
    return float(values[idx[event]] / base_avg - 1.0)


# ----------------------------- What-if khuyến mãi -----------------------------

UPLIFT_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8)
DISCOUNT_GRID = (0.05, 0.10, 0.15, 0.20, 0.25)
REALIZATION = (0.0, 0.5, 1.0, 1.5)


def breakeven_uplift(discount: float, margin: float):
    """Mức tăng cầu tối thiểu để lợi nhuận không giảm. (1+u)(m-d) >= m. Bỏ qua hàng dư."""
    if margin <= discount:
        return None
    return discount / (margin - discount)


def sensitivity_grid(margin: float) -> list[dict]:
    """Đổi lợi nhuận (%) so với không khuyến mãi, theo (mức tăng cầu × mức giảm giá). Không tính hàng dư."""
    rows = []
    for discount in DISCOUNT_GRID:
        cells = []
        for uplift in UPLIFT_GRID:
            change = ((1 + uplift) * (margin - discount) / margin - 1.0) * 100.0
            cells.append({"uplift": uplift, "profit_change_pct": change})
        rows.append({"discount": discount, "cells": cells})
    return rows


def promo_scenarios(forecast_units, price, uplift, discount, margin, multiplier, loss=0.2) -> dict:
    """So sánh có và không khuyến mãi, khi nhập theo dự báo × hệ số đệm.

    lợi nhuận = hàng bán × (giá bán - giá vốn) - hàng dư × giá vốn × loss
    `loss` là tỷ lệ giá vốn của hàng dư bị mất (lưu kho, giảm giá thanh lý). Là giả định của người dùng.
    loss = 0 cho đúng công thức hòa vốn lý thuyết. Cầu cơ sở lấy bằng dự báo (kỳ vọng).
    """
    cost_unit = price * (1.0 - margin)
    qty_base = forecast_units * multiplier
    base_sold = min(qty_base, forecast_units)
    base_leftover = max(qty_base - forecast_units, 0.0)
    base_profit = base_sold * (price - cost_unit) - base_leftover * cost_unit * loss

    qty_promo = forecast_units * (1.0 + uplift) * multiplier
    rows = []
    for ratio in REALIZATION:
        demand = forecast_units * (1.0 + uplift * ratio)
        sold = min(qty_promo, demand)
        leftover = max(qty_promo - demand, 0.0)
        short = max(demand - qty_promo, 0.0)
        profit = sold * (price * (1.0 - discount) - cost_unit) - leftover * cost_unit * loss
        rows.append(
            {
                "realization": ratio,
                "demand_units": demand,
                "sold_units": sold,
                "leftover_units": leftover,
                "shortfall_units": short,
                "profit": profit,
                "profit_change": profit - base_profit,
                "profit_change_pct": (profit - base_profit) / abs(base_profit) * 100.0 if base_profit else None,
            }
        )
    return {
        "baseline": {"order_units": qty_base, "profit": base_profit},
        "promo_order_units": qty_promo,
        "scenarios": rows,
    }
