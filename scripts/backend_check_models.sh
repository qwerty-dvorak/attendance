#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/py-backend"

cd "${BACKEND_DIR}"

echo "[backend_check_models] validating configured model files"
uv run python - <<'PY'
import json
import os
import sys

from config import Config
from face_recognition.detector import SCRFDDetector
from face_recognition.embedders import build_embedders

cfg = Config
result = {
    "model_dir": str(cfg.MODEL_DIR),
    "scrfd_onnx_path": cfg.SCRFD_ONNX_PATH,
    "scrfd_onnx_exists": os.path.exists(cfg.SCRFD_ONNX_PATH),
    "lvface_onnx_path": cfg.LVFACE_ONNX_PATH,
    "lvface_onnx_exists": os.path.exists(cfg.LVFACE_ONNX_PATH),
    "cvlface_pt_path": cfg.CVLFACE_PT_PATH,
    "cvlface_pt_exists": os.path.exists(cfg.CVLFACE_PT_PATH),
    "scrfd_allow_download": bool(cfg.SCRFD_ALLOW_DOWNLOAD),
}

ok = True

try:
    embedders = build_embedders(cfg)
    result["embedders"] = sorted(list(embedders.keys()))
except Exception as exc:
    ok = False
    result["embedders_error"] = str(exc)

try:
    detector = SCRFDDetector(
        model_path=cfg.SCRFD_ONNX_PATH,
        input_size=int(cfg.DETECTION_INPUT_SIZE),
        threshold=float(cfg.DETECTION_THRESHOLD),
        allow_download=bool(cfg.SCRFD_ALLOW_DOWNLOAD),
    )
    result["detector_loaded"] = detector.model is not None
except Exception as exc:
    ok = False
    result["detector_loaded"] = False
    result["detector_error"] = str(exc)

print(json.dumps(result, indent=2))
if not ok:
    sys.exit(2)
PY
