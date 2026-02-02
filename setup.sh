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
#    bash ./setup.sh
#
# Notes:
# - You'll be prompted to install 'uv' if it's missing.
# - Safe to re-run; it updates Python and web dependencies.
# -----------------------------------------------------------------------------
set -euo pipefail

# Check for uv, prompt to install if missing.
if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv from https://astral.sh/uv and re-run ./setup.sh." >&2
  exit 1
fi

# Install web dependencies.
npm ci --prefix apps/ade-web

# Sync Python dependencies into a shared venv (.venv) using per-service lockfiles.
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$PWD/.venv}"
uv --project apps/ade-api sync --dev
uv --project apps/ade-worker sync --dev

# Smoke-check the CLIs.
uv --project apps/ade-api run ade-api --help
uv --project apps/ade-worker run ade-worker --help
