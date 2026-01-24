#!/usr/bin/env bash
set -euo pipefail

#
# scripts/dev/setup.sh
#
# Canonical dev bootstrap:
# - Installs Python deps into the active environment (venv if active, system otherwise)
# - Optionally installs Node tooling + web deps (for apps/ade-web)
#
# Usage:
#   bash scripts/dev/setup.sh           # Python + web deps (default)
#   bash scripts/dev/setup.sh --no-web  # Python only
#
# Environment:
#   UV_SYNC_ARGS="..."                  # extra uv sync args when a venv is active
#   PIP_EXTRA_ARGS="..."                # legacy alias for UV_SYNC_ARGS
#   UV_AUTO_INSTALL=1                   # auto-install uv if missing (default)
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

WITH_WEB=1
if [[ "${1:-}" == "--no-web" ]]; then
  WITH_WEB=0
fi

echo "==> ADE setup"
echo "    repo: ${ROOT_DIR}"
echo "    python: $(python --version 2>/dev/null || true)"

# Ensure data directories exist (compose bind mounts)
mkdir -p data/sql data/azurite

# --- uv + Python env ---
UV_AUTO_INSTALL="${UV_AUTO_INSTALL:-1}"

if ! command -v uv >/dev/null 2>&1; then
  if [[ "${UV_AUTO_INSTALL}" -eq 1 ]]; then
    if ! command -v curl >/dev/null 2>&1; then
      echo "curl is required to install uv automatically." >&2
      exit 1
    fi
    echo "==> Installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  else
    echo "uv is required but was not found on PATH." >&2
    echo "Install uv from https://astral.sh/uv and re-run this script." >&2
    exit 1
  fi
fi

UV_BIN="$(command -v uv)"
SYNC_ARGS="${UV_SYNC_ARGS:-${PIP_EXTRA_ARGS:-}}"

run_maybe_sudo() {
  if [[ "$(id -u)" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo -E "$@"
    else
      "$@"
    fi
  else
    "$@"
  fi
}

active_env=""
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  active_env="${VIRTUAL_ENV}"
elif [[ -n "${CONDA_PREFIX:-}" ]]; then
  active_env="${CONDA_PREFIX}"
fi

echo "==> Syncing Python dependencies (uv)"
if [[ -n "${active_env}" ]]; then
  echo "    Using active environment: ${active_env}"
  sync_cmd=("${UV_BIN}" sync --locked --active)
  # shellcheck disable=SC2086
  if [[ -n "${SYNC_ARGS}" ]]; then
    sync_cmd+=( ${SYNC_ARGS} )
  fi
  "${sync_cmd[@]}"
else
  echo "    No active virtualenv detected; installing into system interpreter."
  echo "    Tip: create/activate a venv first if you want isolation."
  requirements_file="$(mktemp -t ade-requirements.XXXXXX.txt)"
  trap 'rm -f "${requirements_file}"' EXIT
  "${UV_BIN}" export --locked --format requirements.txt --all-packages --output-file "${requirements_file}"
  run_maybe_sudo "${UV_BIN}" pip sync --system --break-system-packages "${requirements_file}"
fi

if [[ "${WITH_WEB}" -eq 1 ]]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is required to set up apps/ade-web." >&2
    echo "- In the devcontainer, Node is installed automatically via a Dev Container Feature." >&2
    echo "- Outside the devcontainer, install Node 24+ (LTS) and re-run this script." >&2
    exit 1
  fi

  # Corepack manages yarn/pnpm versions without apt repos.
  if command -v corepack >/dev/null 2>&1; then
    corepack enable || true
  fi

  if [[ -f "apps/ade-web/package.json" ]]; then
    echo "==> Installing web dependencies (apps/ade-web)"
    pushd apps/ade-web >/dev/null

    if [[ -f "pnpm-lock.yaml" ]]; then
      corepack pnpm install --frozen-lockfile
    elif [[ -f "yarn.lock" ]]; then
      corepack yarn install --frozen-lockfile
    elif [[ -f "package-lock.json" ]]; then
      npm ci
    else
      npm install
    fi

    popd >/dev/null
  else
    echo "!! apps/ade-web/package.json not found; skipping web install."
  fi
fi

echo
echo "==> Done."
echo "    Python deps installed"
echo "    Tip: Use 'bash scripts/db/wait-for-sql.sh' if you need to wait for SQL to be ready."
