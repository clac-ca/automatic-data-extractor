#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
WITH_INFRA=false
FORCE_INFRA=false
OPEN_DEV=false

print_usage() {
  cat <<'EOF'
Usage: ./setup.sh [--with-infra] [--force] [--open]

Options:
  --with-infra   Run `uv run ade infra up -d` after dependency installation.
  --force        Pass `--force` to `ade infra up` (requires --with-infra).
  --open         Start `uv run ade dev --open` after setup completes.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-infra)
      WITH_INFRA=true
      ;;
    --force)
      FORCE_INFRA=true
      ;;
    --open)
      OPEN_DEV=true
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      print_usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "${FORCE_INFRA}" == true && "${WITH_INFRA}" != true ]]; then
  echo "error: --force requires --with-infra" >&2
  exit 1
fi

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

if [[ "${WITH_INFRA}" == true ]]; then
  echo "Starting local infrastructure..."
  infra_cmd=(uv run ade infra up -d)
  if [[ "${FORCE_INFRA}" == true ]]; then
    infra_cmd+=(--force)
  fi
  (cd "${BACKEND_DIR}" && "${infra_cmd[@]}")
fi

if [[ "${OPEN_DEV}" == true ]]; then
  cat <<'EOF'

Setup complete.
Starting ADE dev services with browser auto-open:
  cd backend
  uv run ade dev --open
EOF
  (cd "${BACKEND_DIR}" && uv run ade dev --open)
  exit 0
fi

cat <<'EOF'

Setup complete.
Try:
  cd backend
  uv run ade --help
  uv run ade dev
EOF
