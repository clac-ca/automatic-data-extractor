#!/usr/bin/env bash
set -euo pipefail

#
# scripts/ops/reset-storage.sh
#
# Destructive reset of ADE storage + database tables.
# This wraps the Python implementation to keep the logic centralized.
#
# Usage:
#   bash scripts/ops/reset-storage.sh
#   bash scripts/ops/reset-storage.sh --yes
#   bash scripts/ops/reset-storage.sh --dry-run
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

python -m ade_api.scripts.reset_storage "$@"
