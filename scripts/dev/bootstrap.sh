#!/usr/bin/env bash
set -euo pipefail

# Run from repo root
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "Installing Python deps..."
python -m pip install -U pip
python -m pip install "git+https://github.com/clac-ca/ade-engine.git@${ADE_ENGINE_REF:-main}"
python -m pip install \
  -e "apps/ade-api[dev]" \
  -e "apps/ade-worker[dev]" \
  -e "apps/ade-cli[dev]"

echo "Installing web deps..."
cd apps/ade-web
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

echo "Done."
