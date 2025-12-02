#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

source .venv/bin/activate

features_dir="apps/ade-api/src/ade_api/features"
core_models_dir="apps/ade-api/src/ade_api/core/models"
generated_dir="apps/ade-api/.generated"

if [[ ! -d "${features_dir}" ]]; then
  echo "features directory not found: ${features_dir}" >&2
  exit 1
fi

mkdir -p "${generated_dir}"

# Gather feature folder names (top-level only), skipping cache folders.
mapfile -t features < <(find "${features_dir}" -mindepth 1 -maxdepth 1 -type d ! -name "__pycache__" -printf '%f\n' | sort)

for feature in "${features[@]}"; do
  feature_path="${features_dir}/${feature}"

  # Detect core/common imports used by the feature so we can include those files.
  mapfile -t deps < <(python - <<'PY' "${repo_root}" "${feature_path}"
import ast
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
feature_dir = Path(sys.argv[2])
src_root = repo_root / "apps/ade-api/src"

targets: set[str] = set()

for path in feature_dir.rglob("*.py"):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith(("ade_api.core", "ade_api.common")):
                    targets.add(name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module
            if mod and mod.startswith(("ade_api.core", "ade_api.common")):
                targets.add(mod)

paths: list[Path] = []
for mod in sorted(targets):
    mod_path = src_root / mod.replace(".", "/")
    file_candidate = mod_path.with_suffix(".py")
    if file_candidate.exists():
        paths.append(file_candidate)
        continue
    init_candidate = mod_path / "__init__.py"
    if init_candidate.exists():
        paths.append(init_candidate)

for path in paths:
    print(path.relative_to(repo_root))
PY
  )

  bundle_paths=(
    "${feature_path}"
    "${core_models_dir}"
  )

  declare -A seen=()
  final_paths=()
  for path in "${bundle_paths[@]}" "${deps[@]}"; do
    [[ -z "${path}" ]] && continue
    if [[ -z "${seen[$path]:-}" ]]; then
      seen[$path]=1
      final_paths+=("${path}")
    fi
  done

  output_path="${generated_dir}/${feature}.md"
  echo "Bundling ${feature} -> ${output_path}"
  ade bundle "${final_paths[@]}" --ext py --out "${output_path}" --no-clip --no-show
done

echo "Bundles written to ${generated_dir}"
