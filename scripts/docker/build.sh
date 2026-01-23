#!/usr/bin/env bash
set -euo pipefail

#
# scripts/docker/build.sh
#
# Build the production image using the root Dockerfile.
#
# Usage:
#   bash scripts/docker/build.sh
#   IMAGE_TAG=ade-app:local bash scripts/docker/build.sh
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

IMAGE_TAG="${IMAGE_TAG:-ade-app:local}"

echo "==> Building production image: ${IMAGE_TAG}"
DOCKER_BUILDKIT=1 docker build \
  -t "${IMAGE_TAG}" \
  .
