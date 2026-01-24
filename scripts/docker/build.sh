#!/usr/bin/env bash
set -euo pipefail

#
# scripts/docker/build.sh
#
# Build the production image using the root Dockerfile.
#
# Usage:
#   bash scripts/docker/build.sh
#   ADE_IMAGE=ade-app:local bash scripts/docker/build.sh
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ADE_IMAGE="${ADE_IMAGE:-ade-app:local}"

echo "==> Building production image: ${ADE_IMAGE}"
DOCKER_BUILDKIT=1 docker build \
  -t "${ADE_IMAGE}" \
  .
