from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from _simulator_common import default_base_url, default_test_photos_dir, default_timeout
from config import Config
from utils.image_tools import image_file_to_resized_bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a dummy RFID + ESP32 attendance flow against the API"
    )
    parser.add_argument("--base-url", default=default_base_url())
    parser.add_argument("--rfid", default=Config.SAMPLE_TEACHER_RFID)
    parser.add_argument("--duration", type=int, default=Config.SESSION_DEFAULT_DURATION_MINUTES)
    parser.add_argument("--images-dir", default=str(default_test_photos_dir()))
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--seed-first", action="store_true")
    parser.add_argument("--clear-first", action="store_true")
    return parser.parse_args()


def post_json(url: str, payload: dict) -> dict:
    response = requests.post(url, json=payload, timeout=default_timeout())
    return {"status_code": response.status_code, "payload": response.json()}


def post_frame(base_url: str, session_id: str, image_path: Path) -> dict:
    resized = image_file_to_resized_bytes(
        image_path,
        Config.ESP32_FRAME_WIDTH,
        Config.ESP32_FRAME_HEIGHT,
    )
    response = requests.post(
        f"{base_url}/api/esp32/frame",
        data={"session_id": session_id},
        files={
            Config.ESP32_FRAME_FIELD_NAME: (
                image_path.with_suffix(".jpg").name,
                resized,
                "image/jpeg",
            )
        },
        timeout=default_timeout(),
    )
    return {
        "status_code": response.status_code,
        "image": str(image_path),
        "payload": response.json(),
    }


def collect_images(images_dir: str, limit: int) -> list[Path]:
    root = Path(images_dir).resolve()
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )[: max(1, limit)]


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    report: dict[str, object] = {"base_url": base_url}

    if args.clear_first:
        report["clear"] = post_json(f"{base_url}/api/admin/clear-db", {})

    if args.seed_first:
        report["seed"] = post_json(f"{base_url}/api/admin/seed-sample", {})

    start = post_json(
        f"{base_url}/api/rfid/start-session",
        {
            Config.RFID_UID_FIELD_NAME: args.rfid,
            "duration_minutes": args.duration,
        },
    )
    report["start_session"] = start
    session_id = start["payload"].get("session_id")
    if not session_id:
        print(json.dumps(report, indent=2))
        return 1

    images = collect_images(args.images_dir, args.limit)
    report["frames"] = [post_frame(base_url, session_id, image_path) for image_path in images]

    attendance = requests.get(
        f"{base_url}/api/attendance/{session_id}",
        timeout=default_timeout(),
    )
    report["attendance"] = {
        "status_code": attendance.status_code,
        "payload": attendance.json(),
    }

    print(json.dumps(report, indent=2))
    frames_ok = all(item["payload"].get("success") for item in report["frames"])
    return 0 if start["payload"].get("success") and frames_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
