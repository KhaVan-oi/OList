"""Đọc và kiểm tra query string. SQL chỉ nhận tham số đã qua bước này."""

import re

from flask import request

_STATE = re.compile(r"^[A-Z]{2}$")


def limit_arg(default=10, maximum=50):
    raw = request.args.get("limit")
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"limit là số từ 1 đến {maximum}") from exc
    if not 1 <= value <= maximum:
        raise ValueError(f"limit là số từ 1 đến {maximum}")
    return value


def states_arg(default):
    raw = request.args.get("states")
    if raw is None or raw.strip() == "":
        return list(default)
    states = [part.strip().upper() for part in raw.split(",") if part.strip()]
    if not states or any(_STATE.match(state) is None for state in states):
        raise ValueError("states là mã bang 2 chữ, cách nhau bởi dấu phẩy")
    return states


def state_arg():
    state = (request.args.get("state") or "").strip().upper()
    if _STATE.match(state) is None:
        raise ValueError("state là mã bang 2 chữ")
    return state


def category_arg(default=None):
    category = (request.args.get("category") or default or "").strip()
    if not category or len(category) > 100:
        raise ValueError("category là tên danh mục, tối đa 100 ký tự")
    return category


def year_arg(name, default):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        year = int(raw)
    except ValueError as exc:
        raise ValueError("year nằm trong 2016-2018") from exc
    if year not in (2016, 2017, 2018):
        raise ValueError("year nằm trong 2016-2018")
    return year
