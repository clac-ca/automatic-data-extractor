#!/usr/bin/env bash
set -euo pipefail

#
# scripts/dev/clean.sh
#
# Safe cleanup of build/test artifacts.
#
# By default:
# - Removes Python caches and build outputs
# - Does NOT delete data/ (SQL/Azurite persisted state)
#
# Options:
#   --all     Also remove .venv and node_modules (slow rebuild next time)
#   --data    ALSO delete data/ (DESTRUCTIVE). Requires --yes
#   --yes     Confirm destructive operations
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ALL=0
DATA=0
YES=0

for arg in "$@"; do
  case "${arg}" in
    --all) ALL=1 ;;
    --data) DATA=1 ;;
    --yes) YES=1 ;;
    *) echo "Unknown arg: ${arg}" >&2; exit 1 ;;
  esac
done

echo "==> Cleaning Python caches/artifacts"
rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov            dist build *.egg-info            **/__pycache__ || true

# Remove bytecode files safely (ignore errors)
find . -name '*.pyc' -delete 2>/dev/null || true
find . -name '*.pyo' -delete 2>/dev/null || true

if [[ "${ALL}" -eq 1 ]]; then
  echo "==> Removing .venv and node_modules (requested --all)"
  rm -rf .venv || true
  rm -rf apps/ade-web/node_modules || true
fi

if [[ "${DATA}" -eq 1 ]]; then
  if [[ "${YES}" -ne 1 ]]; then
    echo "!! Refusing to delete data/ without --yes"
    echo "   Re-run: bash scripts/dev/clean.sh --data --yes"
    exit 1
  fi
  echo "==> Deleting data/ (requested --data --yes)"
  rm -rf data || true
fi

echo "==> Done."
