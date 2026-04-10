from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from services.data_management import clear_database


def main() -> None:
    app = create_app()
    with app.app_context():
        result = clear_database()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
