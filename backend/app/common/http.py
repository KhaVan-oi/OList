"""Dịch lỗi truy vấn thành phản hồi HTTP. Mỗi màn chỉ trả dữ liệu của mình."""

from functools import wraps

from flask import jsonify


def screen_endpoint(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValueError as exc:
            return jsonify({"status": "error", "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"status": "error", "error": str(exc)}), 500

    return wrapped


def ok(screen, **payload):
    return jsonify({"status": "ok", "screen": screen, **payload})
