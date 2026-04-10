#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/../models"

PTH_PATH="${MODEL_DIR}/scrfd_34g.pth"
ONNX_PATH="${MODEL_DIR}/scrfd_34g_bnkps.v2.onnx"

if [[ ! -f "${PTH_PATH}" ]]; then
  echo "Missing SCRFD checkpoint: ${PTH_PATH}" >&2
  exit 1
fi

echo "Converting ${PTH_PATH} -> ${ONNX_PATH}"
echo "Requires mmdetection + mmcv environment compatible with scripts/scrfd2onnx.py"
echo "Example: uv run python scripts/scrfd2onnx.py <config.py> ${PTH_PATH} --output-file ${ONNX_PATH} --shape 640 640"
