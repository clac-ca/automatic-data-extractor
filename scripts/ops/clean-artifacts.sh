#!/usr/bin/env bash
set -euo pipefail

#
# scripts/ops/clean-artifacts.sh
#
# Safe cleanup of build/test artifacts (wrapper around `ade clean`).
#
# Usage:
#   bash scripts/ops/clean-artifacts.sh
#   bash scripts/ops/clean-artifacts.sh --all
#   bash scripts/ops/clean-artifacts.sh --yes
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ade clean "$@"
