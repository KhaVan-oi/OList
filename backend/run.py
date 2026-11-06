"""Điểm vào API. Chạy: .venv\\Scripts\\python.exe backend\\run.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
