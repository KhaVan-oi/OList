"""Kiểm tra tiến trình API và kết nối kho."""

from flask import Blueprint, jsonify

from db_connect import get_connection

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as exc:
        return jsonify({"status": "error", "db": str(exc)}), 500
