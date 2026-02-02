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

# Check for uv, prompt to install if missing.
if ! command -v uv >/dev/null 2>&1; then
  echo "Install uv from https://astral.sh/uv and re-run ./setup.sh." >&2
  exit 1
fi

# Install web dependencies.
npm ci --prefix frontend/ade-web

# Sync Python dependencies using the unified backend project (creates backend/.venv).
pushd backend >/dev/null
uv sync

# Smoke-check the CLIs.
uv run ade --help
uv run ade-api --help
uv run ade-worker --help
popd >/dev/null
