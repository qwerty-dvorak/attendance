from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import Config


def default_base_url() -> str:
    return Config.SIMULATOR_API_BASE_URL.rstrip("/")


def default_timeout() -> int:
    return int(Config.SIMULATOR_TIMEOUT_SECONDS)


def default_test_photos_dir() -> Path:
    return Path(Config.TEST_PHOTOS_DIR)
