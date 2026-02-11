#!/usr/bin/env bash
set -euo pipefail

echo "[shell] infra/cloudflare/deploy.sh.example"
bash -n infra/cloudflare/deploy.sh.example

echo "[shell] infra/cloudflare/scripts/prepare-origin-cert-pfx.sh"
bash -n infra/cloudflare/scripts/prepare-origin-cert-pfx.sh

if command -v shellcheck >/dev/null 2>&1; then
  echo "[shellcheck] infra/cloudflare/deploy.sh.example"
  shellcheck infra/cloudflare/deploy.sh.example
  echo "[shellcheck] infra/cloudflare/scripts/prepare-origin-cert-pfx.sh"
  shellcheck infra/cloudflare/scripts/prepare-origin-cert-pfx.sh
fi

echo "Infra Cloudflare validation passed."
