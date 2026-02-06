#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

command -v uv >/dev/null 2>&1 || {
  echo "error: uv is required: https://astral.sh/uv" >&2
  exit 1
}
command -v npm >/dev/null 2>&1 || {
  echo "error: npm is required (Node.js >=20,<23)." >&2
  exit 1
}

echo "Installing web dependencies (frontend/node_modules)..."
npm ci --prefix "${FRONTEND_DIR}"

echo "Installing backend dependencies (backend/.venv)..."
(cd "${BACKEND_DIR}" && uv sync)

cat <<'EOF'

Setup complete.
Try:
  cd backend
  uv run ade --help
  uv run ade dev
EOF
