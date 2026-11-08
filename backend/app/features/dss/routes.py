"""DSS nhập hàng và khuyến mãi. Dữ liệu từ dw.v_dss_monthly_demand qua QueryGateway.

Endpoint:
    /api/dss/options    bang, danh mục, khoảng tháng dùng cho DSS
    /api/dss/forecast   dự báo tháng tới, backtest, lượng nhập đề xuất, đường đánh đổi
    /api/dss/accuracy   độ chính xác backtest theo mức tổng hợp (tổng, bang, danh mục)
    /api/dss/whatif     khuyến mãi: hòa vốn, độ nhạy, kịch bản hàng dư và thiếu
"""

import re

from flask import Blueprint, request

from app.common.http import ok, screen_endpoint
from app.common.query_gateway import QueryGateway
from app.features.dss import forecast as fc

# Cửa sổ lịch sử đủ tháng. 2016 quá thưa (có tháng không có đơn), 2018-09 trở đi chưa có đơn delivered.
HISTORY_START = "2017-01"
HISTORY_END = "2018-08"

_STATE = re.compile(r"^[A-Z]{2}$")
_METRICS = {"units": "units", "revenue": "revenue"}  # whitelist cột, không nối chuỗi từ request
_TOP_STATES = 10
_TOP_CATEGORIES = 15


def _months():
    year, month = (int(part) for part in HISTORY_START.split("-"))
    end_year, end_month = (int(part) for part in HISTORY_END.split("-"))
    out = []
    while (year, month) <= (end_year, end_month):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


def _next_month(label):
    year, month = (int(part) for part in label.split("-"))
    month += 1
    if month == 13:
        year, month = year + 1, 1
    return f"{year:04d}-{month:02d}"


def _bounds():
    return f"{HISTORY_START}-01", f"{HISTORY_END}-01"


def _scope():
    scope = request.args.get("scope", "total")
    value = (request.args.get("value") or "").strip()
    if scope == "total":
        return "total", ""
    if scope == "state":
        value = value.upper()
        if _STATE.match(value) is None:
            raise ValueError("value là mã bang 2 chữ khi scope=state")
        return "state", value
    if scope == "category":
        if not value or len(value) > 100:
            raise ValueError("value là tên danh mục (tối đa 100 ký tự) khi scope=category")
        return "category", value
    raise ValueError("scope phải là total, state hoặc category")


def _metric():
    metric = request.args.get("metric", "units")
    if metric not in _METRICS:
        raise ValueError("metric phải là units hoặc revenue")
    return metric


def _number(name, default, low, high, scale=1.0):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} là số từ {low} đến {high}") from exc
    if not low <= value <= high:
        raise ValueError(f"{name} là số từ {low} đến {high}")
    return value / scale


def _series(gateway, scope, value):
    """Chuỗi tháng đầy đủ (điền 0 cho tháng không có đơn) của units và revenue."""
    start, end = _bounds()
    filters = {"total": "", "state": "AND customer_state = %s", "category": "AND category = %s"}
    params = [start, end] + ([value] if scope != "total" else [])
    rows = gateway.fetch_all(
        f"""
        SELECT to_char(month_start, 'YYYY-MM') AS month,
               sum(units) AS units,
               sum(revenue) AS revenue
        FROM dw.v_dss_monthly_demand
        WHERE month_start >= %s AND month_start <= %s {filters[scope]}
        GROUP BY 1
        """,
        tuple(params),
    )
    by_month = {row["month"]: row for row in rows}
    months = _months()
    return {
        "months": months,
        "units": [float(by_month.get(m, {}).get("units") or 0) for m in months],
        "revenue": [float(by_month.get(m, {}).get("revenue") or 0) for m in months],
    }


def _panel(gateway, dimension, top_n):
    """Các chuỗi của top_n bang hoặc danh mục lớn nhất (theo doanh thu trong cửa sổ)."""
    column = {"state": "customer_state", "category": "category"}[dimension]
    start, end = _bounds()
    rows = gateway.fetch_all(
        f"""
        WITH top AS (
            SELECT {column} AS key
            FROM dw.v_dss_monthly_demand
            WHERE month_start >= %s AND month_start <= %s AND {column} IS NOT NULL
            GROUP BY {column}
            ORDER BY sum(revenue) DESC, {column}
            LIMIT %s
        )
        SELECT to_char(v.month_start, 'YYYY-MM') AS month,
               v.{column} AS key,
               sum(v.units) AS units,
               sum(v.revenue) AS revenue
        FROM dw.v_dss_monthly_demand v
        JOIN top ON top.key = v.{column}
        WHERE v.month_start >= %s AND v.month_start <= %s
        GROUP BY 1, 2
        """,
        (start, end, top_n, start, end),
    )
    months = _months()
    keys = []
    for row in rows:
        if row["key"] not in keys:
            keys.append(row["key"])
    out = {}
    for key in keys:
        cells = {row["month"]: row for row in rows if row["key"] == key}
        out[key] = {
            "units": [float(cells.get(m, {}).get("units") or 0) for m in months],
            "revenue": [float(cells.get(m, {}).get("revenue") or 0) for m in months],
        }
    return months, out


def _with_months(rows, months):
    return [{**row, "month": months[row["index"]]} for row in rows]


def _metrics_table(rows):
    ex_event = [row for row in rows if row["month"] not in fc.EVENT_MONTHS]
    table = []
    for model in fc.MODELS:
        full = fc.model_metrics(rows, model)
        trimmed = fc.model_metrics(ex_event, model)
        table.append(
            {
                "model": model,
                "wape": full["wape"],
                "mape": full["mape"],
                "bias": full["bias"],
                "wape_ex_event": trimmed["wape"],
                "n": full["n"],
            }
        )
    return table


def _model():
    model = request.args.get("model", "blend")
    if model != "auto" and model not in fc.MODELS:
        raise ValueError("model phải là auto, naive, ma3, holt hoặc blend")
    return model


def _exclude_event():
    return request.args.get("exclude_event", "0") in ("1", "true")


def _forecast_bundle(series, metric, service, exclude_event=False, model="blend"):
    values = series[metric]
    months = series["months"]
    rows = _with_months(fc.backtest(values), months)
    best = fc.pick_model(rows)
    chosen = best if model == "auto" else model
    next_forecasts = fc.forecast_all(values)
    error_rows = [row for row in rows if row["month"] not in fc.EVENT_MONTHS] if exclude_event else rows
    errors = fc.relative_errors(error_rows, chosen)
    plan = fc.order_plan(next_forecasts[chosen], errors, service)
    return {
        "rows": rows,
        "error_rows": error_rows,
        "chosen": chosen,
        "best": best,
        "next_forecasts": next_forecasts,
        "errors": errors,
        "plan": plan,
    }


def create_dss_blueprint(gateway: QueryGateway):
    bp = Blueprint("dss", __name__)

    @bp.route("/api/dss/options", methods=["GET"])
    @screen_endpoint
    def options():
        start, end = _bounds()
        states = gateway.fetch_all(
            """
            SELECT customer_state AS code, sum(units) AS units, round(sum(revenue), 2) AS revenue
            FROM dw.v_dss_monthly_demand
            WHERE month_start >= %s AND month_start <= %s AND customer_state IS NOT NULL
            GROUP BY customer_state
            ORDER BY sum(revenue) DESC, customer_state
            """,
            (start, end),
        )
        categories = gateway.fetch_all(
            """
            SELECT category, sum(units) AS units, round(sum(revenue), 2) AS revenue
            FROM dw.v_dss_monthly_demand
            WHERE month_start >= %s AND month_start <= %s
            GROUP BY category
            ORDER BY sum(revenue) DESC, category
            LIMIT 30
            """,
            (start, end),
        )
        months = _months()
        return ok(
            "dss-options",
            first_month=months[0],
            last_month=months[-1],
            next_month=_next_month(months[-1]),
            models=list(fc.MODELS),
            event_months=list(fc.EVENT_MONTHS),
            states=states,
            categories=categories,
        )

    @bp.route("/api/dss/forecast", methods=["GET"])
    @screen_endpoint
    def forecast():
        scope, value = _scope()
        metric = _metric()
        service = _number("service", 0.9, 0.5, 0.99)
        exclude_event = _exclude_event()
        model = _model()
        series = _series(gateway, scope, value)
        if sum(series[metric]) <= 0:
            raise ValueError("Không có dữ liệu trong khoảng lịch sử cho lựa chọn này")
        bundle = _forecast_bundle(series, metric, service, exclude_event, model)
        months = series["months"]
        values = series[metric]
        chosen = bundle["chosen"]
        rows = bundle["rows"]
        return ok(
            "dss-forecast",
            scope=scope,
            value=value or None,
            metric=metric,
            service=service,
            exclude_event=exclude_event,
            window={"first": months[0], "last": months[-1], "next": _next_month(months[-1])},
            history=[{"month": m, "actual": v} for m, v in zip(months, values)],
            backtest=[
                {
                    "month": row["month"],
                    "actual": row["actual"],
                    "chosen": row[chosen],
                    **{model: row[model] for model in fc.MODELS},
                }
                for row in rows
            ],
            metrics=_metrics_table(rows),
            chosen_model=chosen,
            best_model=bundle["best"],
            next={
                "month": _next_month(months[-1]),
                "forecast": bundle["next_forecasts"][chosen],
                "by_model": bundle["next_forecasts"],
            },
            order=bundle["plan"],
            tradeoff=fc.tradeoff(bundle["error_rows"], chosen),
            event_uplift=fc.event_uplift(months, values),
            note=(
                "Dự báo trước 1 tháng, backtest trượt theo thời gian. Mặc định dùng blend (trung bình naive và Holt). "
                "Chế độ auto chọn mô hình có WAPE thấp nhất trên chính các tháng backtest, nên số đo hơi lạc quan. "
                "Lượng đệm học từ sai số thực nghiệm."
            ),
        )

    @bp.route("/api/dss/accuracy", methods=["GET"])
    @screen_endpoint
    def accuracy():
        metric = _metric()
        total_series = _series(gateway, "total", "")
        levels = []

        def summarize(label, series_list, months):
            pooled = {model: [] for model in fc.MODELS}
            per_series = []
            for name, values in series_list:
                rows = _with_months(fc.backtest(values), months)
                per_series.append(
                    {
                        "name": name,
                        "wape": fc.model_metrics(rows, "blend")["wape"],
                        "wape_naive": fc.model_metrics(rows, "naive")["wape"],
                    }
                )
                for model in fc.MODELS:
                    pooled[model].extend(
                        {"actual": row["actual"], model: row[model], "month": row["month"]} for row in rows
                    )
            models = []
            for model in fc.MODELS:
                rows = pooled[model]
                trimmed = [row for row in rows if row["month"] not in fc.EVENT_MONTHS]
                full = fc.model_metrics(rows, model)
                cut = fc.model_metrics(trimmed, model)
                models.append({"model": model, "wape": full["wape"], "wape_ex_event": cut["wape"]})
            return {"level": label, "n_series": len(series_list), "models": models, "series": per_series}

        months = total_series["months"]
        levels.append(summarize("Tổng toàn kho", [("Tổng", total_series[metric])], months))
        state_months, states = _panel(gateway, "state", _TOP_STATES)
        levels.append(
            summarize(f"{len(states)} bang lớn", [(key, data[metric]) for key, data in states.items()], state_months)
        )
        cat_months, cats = _panel(gateway, "category", _TOP_CATEGORIES)
        levels.append(
            summarize(f"{len(cats)} danh mục lớn", [(key, data[metric]) for key, data in cats.items()], cat_months)
        )
        n_test = len(months) - fc.MIN_TRAIN
        return ok(
            "dss-accuracy",
            metric=metric,
            levels=levels,
            test_window={"first": months[fc.MIN_TRAIN], "last": months[-1], "n_months": n_test},
            event_months=list(fc.EVENT_MONTHS),
            note=(
                "WAPE = tổng |thực tế - dự báo| / tổng thực tế, gộp qua mọi chuỗi và tháng. "
                "wape_ex_event bỏ các tháng Black Friday 2017 và tháng sau. Hai cột báo cáo song song, không chọn lọc."
            ),
        )

    @bp.route("/api/dss/whatif", methods=["GET"])
    @screen_endpoint
    def whatif():
        scope, value = _scope()
        service = _number("service", 0.9, 0.5, 0.99)
        uplift = _number("uplift", 0.5, 0, 300, scale=100.0)
        discount = _number("discount", 0.10, 0, 60, scale=100.0)
        margin = _number("margin", 0.35, 1, 90, scale=100.0)
        loss = _number("loss", 0.20, 0, 100, scale=100.0)
        exclude_event = _exclude_event()
        model = _model()
        series = _series(gateway, scope, value)
        if sum(series["units"]) <= 0:
            raise ValueError("Không có dữ liệu trong khoảng lịch sử cho lựa chọn này")
        bundle = _forecast_bundle(series, "units", service, exclude_event, model)
        forecast_units = bundle["next_forecasts"][bundle["chosen"]]
        recent_units = sum(series["units"][-3:])
        recent_revenue = sum(series["revenue"][-3:])
        if recent_units <= 0:
            raise ValueError("Ba tháng gần nhất không có đơn nên không ước được giá bán")
        price = recent_revenue / recent_units
        plan = bundle["plan"]
        promo = fc.promo_scenarios(forecast_units, price, uplift, discount, margin, plan["multiplier"], loss)
        return ok(
            "dss-whatif",
            scope=scope,
            value=value or None,
            month=_next_month(series["months"][-1]),
            inputs={
                "uplift": uplift,
                "discount": discount,
                "margin": margin,
                "service": service,
                "loss": loss,
                "exclude_event": exclude_event,
                "model": bundle["chosen"],
            },
            baseline_forecast_units=forecast_units,
            avg_price=price,
            order_multiplier=plan["multiplier"],
            breakeven_uplift=fc.breakeven_uplift(discount, margin),
            observed_event_uplift=fc.event_uplift(series["months"], series["units"]),
            sensitivity=fc.sensitivity_grid(margin),
            promo=promo,
            note=(
                "Mức tăng cầu, mức giảm giá, biên lợi nhuận và tổn thất hàng dư là GIẢ ĐỊNH của người dùng, không suy ra từ dữ liệu. "
                "Kho không có thí nghiệm khuyến mãi. Tháng Black Friday 2017 chỉ là điểm tham chiếu quan sát."
            ),
        )

    return bp
