#!/usr/bin/env bash
set -euo pipefail

#
# scripts/docker/build-image.sh
#
# Build the production image using the root Dockerfile.
#
# Usage:
#   bash scripts/docker/build-image.sh
#

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

echo "==> Building production image: ade-app:local"
DOCKER_BUILDKIT=1 docker build -t ade-app:local .
