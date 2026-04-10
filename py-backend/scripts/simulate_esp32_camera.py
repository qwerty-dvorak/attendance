from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from _simulator_common import default_base_url, default_test_photos_dir, default_timeout
from config import Config
from utils.image_tools import image_file_to_resized_bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate ESP32 camera frame uploads")
    parser.add_argument("--base-url", default=default_base_url())
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--image", help="Single image path to upload")
    parser.add_argument(
        "--images-dir",
        default=str(default_test_photos_dir()),
        help="Directory of test images to upload in sorted order",
    )
    parser.add_argument("--limit", type=int, default=1)
    return parser.parse_args()


def collect_images(args: argparse.Namespace) -> list[Path]:
    if args.image:
        return [Path(args.image).resolve()]

    root = Path(args.images_dir).resolve()
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )[: max(1, args.limit)]


def upload_image(base_url: str, session_id: str, image_path: Path) -> dict:
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
    payload = response.json()
    payload["source_image"] = str(image_path)
    payload["http_status"] = response.status_code
    return payload


def main() -> int:
    args = parse_args()
    images = collect_images(args)
    if not images:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"No test images found in {args.images_dir}",
                },
                indent=2,
            )
        )
        return 2

    results = [upload_image(args.base_url, args.session_id, path) for path in images]
    success = all(row.get("success") for row in results)
    print(json.dumps({"success": success, "results": results}, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
