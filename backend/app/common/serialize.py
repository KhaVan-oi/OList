"""Chuyển giá trị PostgreSQL sang kiểu JSON được."""

from datetime import date, datetime
from decimal import Decimal


def jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
