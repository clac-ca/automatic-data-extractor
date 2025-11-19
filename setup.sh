#!/usr/bin/env bash
set -euo pipefail

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend packages
pip install -U pip setuptools wheel
pip install -e apps/ade-cli
pip install -e apps/ade-engine
pip install -e apps/ade-api

# Install frontend dependencies
(cd apps/ade-web && npm install)

# Verify CLI
ade --help