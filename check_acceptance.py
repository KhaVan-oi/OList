"""Chạy lại nghiệm thu kho (sql/dw/03_validate.sql) mà không nạp lại dữ liệu. Thoát mã 1 nếu có tiêu chí sai."""
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from db_connect import get_connection
from etl_pipeline import run_acceptance_tests


def main() -> int:
    try:
        conn = get_connection()
    except Exception as e:
        print(f"[-] Không kết nối được database: {e}")
        return 1
    try:
        with conn.cursor() as cur:
            run_acceptance_tests(cur)
        return 0
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1
    finally:
        conn.rollback()  # chỉ đọc; không để lại giao dịch mở
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
