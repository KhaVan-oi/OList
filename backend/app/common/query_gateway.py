"""Cổng đọc kho. Mọi màn (overview, thời gian, khu vực, khách) chỉ gọi gateway — không mở psycopg2 trong route."""

from db_connect import get_connection

from app.common.serialize import jsonable


class QueryGateway:
    def fetch_all(self, sql, params=()):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [desc[0] for desc in cur.description]
                return [
                    {column: jsonable(value) for column, value in zip(columns, row)}
                    for row in cur.fetchall()
                ]
        finally:
            conn.close()

    def fetch_one(self, sql, params=()):
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else {}
