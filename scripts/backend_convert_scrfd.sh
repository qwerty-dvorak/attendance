#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/py-backend"
MODEL_DIR="${ROOT_DIR}/models"

DEFAULT_CONFIG="${BACKEND_DIR}/scripts/scrfd_34g_export_config.py"
SCRFD_CONFIG="${1:-${DEFAULT_CONFIG}}"

if [[ ! -f "${SCRFD_CONFIG}" ]]; then
  echo "Config file not found: ${SCRFD_CONFIG}" >&2
  exit 1
fi

if [[ ! -f "${MODEL_DIR}/scrfd_34g.pth" ]]; then
  echo "Missing model checkpoint: ${MODEL_DIR}/scrfd_34g.pth" >&2
  exit 1
fi

if [[ -f "${MODEL_DIR}/scrfd_34g.onnx" ]]; then
  echo "[backend_convert_scrfd] existing ONNX found: ${MODEL_DIR}/scrfd_34g.onnx"
  echo "[backend_convert_scrfd] conversion skipped"
  exit 0
fi

cd "${BACKEND_DIR}"

echo "[backend_convert_scrfd] converting SCRFD with fixed shape 640x640"
uv run python scripts/scrfd2onnx.py \
  "${SCRFD_CONFIG}" \
  "${MODEL_DIR}/scrfd_34g.pth" \
  --output-file "${MODEL_DIR}/scrfd_34g_bnkps.v2.onnx" \
  --shape 640 640

echo "[backend_convert_scrfd] done: ${MODEL_DIR}/scrfd_34g_bnkps.v2.onnx"
echo "[backend_convert_scrfd] you can point SCRFD_ONNX_PATH to: ${MODEL_DIR}/scrfd_34g_bnkps.v2.onnx"
