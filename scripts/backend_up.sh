#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/py-backend"

cd "${BACKEND_DIR}"

echo "[backend_up] syncing uv environment"
uv sync

echo "[backend_up] validating model availability"
"${ROOT_DIR}/scripts/backend_check_models.sh" || true

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "[backend_up] created .env from .env.example"
  else
    echo "[backend_up] missing .env and .env.example" >&2
    exit 1
  fi
fi

echo "[backend_up] starting Flask backend"
exec uv run python run.py
