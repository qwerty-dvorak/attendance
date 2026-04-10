from __future__ import annotations

import argparse
import json

import requests

from _simulator_common import default_base_url, default_timeout
from config import Config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate RFID session start")
    parser.add_argument("--base-url", default=default_base_url())
    parser.add_argument("--rfid", default=Config.SAMPLE_TEACHER_RFID)
    parser.add_argument("--duration", type=int, default=Config.SESSION_DEFAULT_DURATION_MINUTES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    response = requests.post(
        f"{args.base_url}/api/rfid/start-session",
        json={
            Config.RFID_UID_FIELD_NAME: args.rfid,
            "duration_minutes": args.duration,
        },
        timeout=default_timeout(),
    )
    print(json.dumps(response.json(), indent=2))
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
