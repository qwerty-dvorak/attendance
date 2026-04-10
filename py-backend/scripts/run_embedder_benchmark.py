from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from services.runtime import get_attendance_service


def _collect_samples() -> list[dict]:
    roots = [
        Path("cvlface/apps/verification/example/images"),
        Path("cvlface/apps/face_alignment/example/images"),
    ]
    samples: list[dict] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for image_path in sorted(root.iterdir()):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            resolved = str(image_path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            samples.append({"image_path": resolved})
    return samples


def main() -> int:
    app = create_app()
    samples = _collect_samples()
    if not samples:
        print(
            json.dumps(
                {"success": False, "error": "No benchmark images found"}, indent=2
            )
        )
        return 2

    with app.app_context():
        service = get_attendance_service()
        result = service.benchmark_embedders(samples)
        print(
            json.dumps(
                {"success": True, **result, "num_samples": len(samples)}, indent=2
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
