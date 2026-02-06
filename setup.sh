#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# ADE local setup
#
# Recommended: use the devcontainer (preconfigured, reproducible).
# This script is only needed when working outside the devcontainer.
# Or you wish to reinstall dependencies in an existing devcontainer.
#
# Local setup steps:
# 1) Install Python 3.14+
# 2) Install Node.js 22+
# 3) Run:
#
#    bash ./setup.sh
#
# Notes:
# - You'll be prompted to install 'uv' if it's missing.
# -----------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

# Check for uv, prompt to install if missing.
if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv from https://astral.sh/uv and re-run ./setup.sh." >&2
  exit 1
fi

# Install web dependencies.
npm ci --prefix "${ROOT_DIR}/frontend/ade-web"

# Sync Python dependencies in backend/.venv.
uv sync --project "${BACKEND_DIR}"
