#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[project_clean] cleaning backend"
"${ROOT_DIR}/scripts/backend_clean.sh"

echo "[project_clean] removing report build artifacts"
rm -f "${ROOT_DIR}/report"/*.aux "${ROOT_DIR}/report"/*.log "${ROOT_DIR}/report"/*.out "${ROOT_DIR}/report"/*.toc "${ROOT_DIR}/report"/*.lot "${ROOT_DIR}/report"/*.lof "${ROOT_DIR}/report"/*.pdf

echo "[project_clean] done"
