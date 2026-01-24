#!/usr/bin/env bash
set -euo pipefail

#
# scripts/docker/run.sh
#
# Runs the production image locally.
#
# This is intentionally minimal and may need adjustment based on how the app starts.
#
# Usage:
#   ADE_IMAGE=ade-app:local bash scripts/docker/run.sh
#
# By default it exposes port 8000. If your API uses a different port, change it here.
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ADE_IMAGE="${ADE_IMAGE:-ade-app:local}"

ENV_ARGS=()
if [[ -f ".env" ]]; then
  ENV_ARGS=(--env-file .env)
else
  echo "==> .env not found; running with defaults"
fi

echo "==> Running ${ADE_IMAGE}"
docker run --rm -it \
  "${ENV_ARGS[@]}" \
  -p 8000:8000 \
  "${ADE_IMAGE}"
