#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# ADE Local Bootstrap Script
# -----------------------------------------------------------------------------
# Bootstraps a complete ADE developer environment in one shot:
#   1. Creates and activates a local Python virtual environment
#   2. Upgrades pip/setuptools/wheel for modern packaging support
#   3. Installs ADE components (CLI, schemas, engine, API) in editable mode
#   4. Installs frontend dependencies for the web app
#   5. Verifies installation by invoking `ade --help`
#
# Usage:
#   ./setup.sh
#
# Tip: Run this script from the project root after cloning the repository.
#      It’s safe to re-run — dependencies will be upgraded in place.
# -----------------------------------------------------------------------------

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e apps/ade-cli
pip install -e packages/ade-schemas
pip install -e apps/ade-engine
pip install -e apps/ade-api
(cd apps/ade-web && npm install)

ade --help
