#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
.venv/bin/pip install -U pip setuptools wheel
.venv/bin/pip install -e apps/ade-cli
.venv/bin/pip install -e packages/ade-schemas
.venv/bin/pip install -e apps/ade-engine
.venv/bin/pip install -e apps/ade-api
(cd apps/ade-web && npm install)

echo "Activate and run:"
echo "  source .venv/bin/activate"
echo "  ade --help"
echo "  ade dev"
