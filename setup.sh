#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Install Python dev dependencies (editable installs).
python -m pip install -e apps/ade-cli[dev]
python -m pip install -e apps/ade-api[dev]
python -m pip install -e apps/ade-worker[dev]

# Optional: same installs with uv (uncomment to use).
# uv pip install -e apps/ade-cli[dev]
# uv pip install -e apps/ade-api[dev]
# uv pip install -e apps/ade-worker[dev]

# Install web dependencies.
npm ci --prefix apps/ade-web
