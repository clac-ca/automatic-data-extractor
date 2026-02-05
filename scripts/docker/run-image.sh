#!/usr/bin/env bash
set -euo pipefail

#
# scripts/docker/run-image.sh
#
# Runs the production image locally.
#
# This is intentionally minimal and may need adjustment based on how the app starts.
#
# Usage:
#   bash scripts/docker/run-image.sh
#
# By default it exposes port 8000. If your API uses a different port, change it here.
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f ".env" ]]; then
  echo "==> .env not found; create one from .env.example first" >&2
  exit 1
fi

IMAGE="${ADE_IMAGE:-automatic-data-extractor:local}"

echo "==> Running ${IMAGE}"
docker run \
  --rm -it \
  --env-file .env \
  -e ADE_DATA_DIR=/var/lib/ade/data \
  -p 8000:8000 \
  -v "${ROOT_DIR}/backend/data:/var/lib/ade/data" \
  "${IMAGE}"
