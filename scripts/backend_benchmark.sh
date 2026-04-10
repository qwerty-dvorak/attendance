#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/py-backend"

cd "${BACKEND_DIR}"

echo "[backend_benchmark] running local embedder benchmark"
uv run python scripts/run_embedder_benchmark.py
