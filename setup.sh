#!/usr/bin/env bash
set -euo pipefail

# For local development, recommend using .devcontainer in VS Code (requires Docker; automatically sets up environment).
# Alternatively, ensure you have Python 3.10+ and Node.js 22+ installed and run this script

# Optionally create and activate a virtual environment.
# python -m venv .venv && source .venv/bin/activate

python -m pip install -e apps/ade-api[dev]
python -m pip install -e apps/ade-worker[dev]

# Optional: same installs with uv (uncomment to use).
# uv pip install -e apps/ade-api[dev]
# uv pip install -e apps/ade-worker[dev]

# Install web dependencies.
npm ci --prefix apps/ade-web
