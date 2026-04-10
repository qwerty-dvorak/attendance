#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/py-backend"

cd "${BACKEND_DIR}"

echo "[backend_clean] removing runtime/cache artifacts"
rm -rf .pytest_cache .mypy_cache
rm -rf __pycache__ api/__pycache__ services/__pycache__ face_recognition/__pycache__ email_service/__pycache__
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

echo "[backend_clean] removing generated database and uploads"
rm -f attendance.db
rm -rf uploads/sessions/* uploads/students/*

echo "[backend_clean] done"
