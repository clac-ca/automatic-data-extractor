#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

# ADE tooling in this repo lives inside the root virtualenv.
# source ensures the `ade` CLI is available.
source .venv/bin/activate

generated_dir="${repo_root}/.generated"
mkdir -p "${generated_dir}"

# Start with the canonical ADE API README.
logging_paths=("apps/ade-api/README.md")

# Include the key Python sources that define ADE's logging setup and behavior.
logging_files=(
  "apps/ade-api/src/ade_api/settings.py"
  "apps/ade-api/src/ade_api/main.py"
  "apps/ade-api/src/ade_api/shared/core/logging.py"
  "apps/ade-api/src/ade_api/shared/core/middleware.py"
)

for path in "${logging_files[@]}"; do
  if [[ ! -f "${path}" ]]; then
    echo "required logging source missing: ${path}" >&2
    exit 1
  fi
done

logging_paths+=("${logging_files[@]}")

ade bundle "${logging_paths[@]}" \
  --out "${generated_dir}/ade-api-logging.md" \
  --no-show
