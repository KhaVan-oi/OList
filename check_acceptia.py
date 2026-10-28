import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from db_connect import get_connection
from etl_pipeline import run_acceptance_tests


def main():
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            run_acceptance_tests(cur)
        conn.close()
    except Exception as e:
        print(f"[-] Lỗi kết nối hoặc truy vấn: {e}")

if __name__ == "__main__":
    main()
