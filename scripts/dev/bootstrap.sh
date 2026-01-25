#!/usr/bin/env bash
set -euo pipefail

#
# scripts/dev/bootstrap.sh
#
# Canonical dev bootstrap:
# - Installs Python deps into the active environment (venv if active, system otherwise)
# - Optionally installs Node tooling + web deps (for apps/ade-web)
#
# Usage:
#   bash scripts/dev/bootstrap.sh           # Python + web deps (default)
#   bash scripts/dev/bootstrap.sh --no-web  # Python only
#
# Environment:
#   PIP_INSTALL_ARGS="..."            # extra pip install args
#   PIP_EXTRA_ARGS="..."              # legacy alias for PIP_INSTALL_ARGS
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



# --- Python env ---
PIP_INSTALL_ARGS="${PIP_INSTALL_ARGS:-${PIP_EXTRA_ARGS:-}}"

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

echo "==> Installing Python dependencies (pip)"
if [[ -n "${active_env}" ]]; then
  echo "    Using active environment: ${active_env}"
  install_cmd=(python -m pip install)
  # shellcheck disable=SC2086
  if [[ -n "${PIP_INSTALL_ARGS}" ]]; then
    install_cmd+=( ${PIP_INSTALL_ARGS} )
  fi
  install_cmd+=(
    -e "apps/ade-cli[dev]"
    -e "apps/ade-api[dev]"
    -e "apps/ade-worker[dev]"
  )
  "${install_cmd[@]}"
else
  echo "    No active virtualenv detected; installing into system interpreter."
  echo "    Tip: create/activate a venv first if you want isolation."
  install_cmd=(python -m pip install)
  # shellcheck disable=SC2086
  if [[ -n "${PIP_INSTALL_ARGS}" ]]; then
    install_cmd+=( ${PIP_INSTALL_ARGS} )
  fi
  install_cmd+=(
    -e "apps/ade-cli[dev]"
    -e "apps/ade-api[dev]"
    -e "apps/ade-worker[dev]"
  )
  run_maybe_sudo "${install_cmd[@]}"
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
echo "    Tip: Postgres initializes via the devcontainer compose `postgres` service."
