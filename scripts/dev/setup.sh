#!/usr/bin/env bash
set -euo pipefail

#
# scripts/dev/setup.sh
#
# Canonical dev bootstrap:
# - Creates/updates a local venv at .venv
# - Installs Python deps (idempotent)
# - Optionally installs Node tooling + web deps (for apps/ade-web)
#
# Usage:
#   bash scripts/dev/setup.sh           # Python only
#   bash scripts/dev/setup.sh --web     # Python + Node + web deps
#
# Environment:
#   PIP_EXTRA_ARGS="..."                # extra pip args (e.g. --index-url ...)
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

WITH_WEB=0
if [[ "${1:-}" == "--web" ]]; then
  WITH_WEB=1
fi

echo "==> ADE setup"
echo "    repo: ${ROOT_DIR}"
echo "    python: $(python --version 2>/dev/null || true)"

# Ensure data directories exist (compose bind mounts)
mkdir -p data/sql data/azurite

# --- Python venv ---
if [[ ! -d ".venv" ]]; then
  echo "==> Creating venv (.venv)"
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

echo "==> Installing Python dependencies (editable)"
python -m pip install \
  -e "apps/ade-cli[dev]" \
  -e "apps/ade-api[dev]" \
  -e "apps/ade-worker[dev]" \
  ${PIP_EXTRA_ARGS:-}

# --- Optional web tooling ---
if [[ "${WITH_WEB}" -eq 1 ]]; then
  echo "==> Installing Node.js (Debian package) + enabling Corepack"
  # Keep this explicit and opt-in to keep the dev image lean.
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends nodejs npm
  sudo rm -rf /var/lib/apt/lists/*

  # Corepack manages yarn/pnpm versions without apt repos.
  if command -v corepack >/dev/null 2>&1; then
    corepack enable || true
  fi

  if [[ -f "apps/ade-web/package.json" ]]; then
    echo "==> Installing web dependencies (apps/ade-web)"
    pushd apps/ade-web >/dev/null

    if [[ -f "pnpm-lock.yaml" ]]; then
      corepack pnpm install --frozen-lockfile
      corepack pnpm run build || true
    elif [[ -f "yarn.lock" ]]; then
      corepack yarn install --frozen-lockfile
      corepack yarn run build || true
    elif [[ -f "package-lock.json" ]]; then
      npm ci
      npm run build || true
    else
      npm install
      npm run build || true
    fi

    popd >/dev/null
  else
    echo "!! apps/ade-web/package.json not found; skipping web install."
  fi
fi

echo
echo "==> Done."
echo "    Venv: .venv"
echo "    Tip: Use 'bash scripts/db/wait-for-sql.sh' if you need to wait for SQL to be ready."
