#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

# Refresh ADE engine docs bundle. Assumes .venv is present at repo root.
source .venv/bin/activate

generated_dir="apps/ade-engine/.generated"
mkdir -p "${generated_dir}"

ade bundle apps/ade-engine/README.md \
  --dir apps/ade-engine/docs \
  --ext md \
  --out "${generated_dir}/ade-engine-docs-bundle.md" \
  --no-show
