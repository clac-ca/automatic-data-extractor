#!/usr/bin/env bash
set -euo pipefail

# Run: bash ./setup.sh

# For local development, recommend using .devcontainer in VS Code (requires Docker; automatically sets up environment).
# Alternatively, ensure you have Python 3.14+ and Node.js 22+ installed and run this script.

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://astral.sh/uv and re-run ./setup.sh." >&2
  exit 1
fi

# Sync Python dependencies into the project venv (.venv) using the lockfile.
uv sync --dev

# Install web dependencies.
npm ci --prefix apps/ade-web
