#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

# Bundle ADE web source by logical areas. Assumes .venv is present at repo root.
source .venv/bin/activate

generated_dir="apps/ade-web/.generated"
mkdir -p "${generated_dir}"

# App shell + navigation + bootstrap
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/main.tsx \
  --dir apps/ade-web/src/app \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-app.md" \
  --no-clip --no-show

# Shared data layer (API clients)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/shared/api \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-shared-api.md" \
  --no-clip --no-show

# Shared auth + notifications + storage helpers
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/shared/auth \
  --dir apps/ade-web/src/shared/notifications \
  apps/ade-web/src/shared/storage.ts \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-shared-core.md" \
  --no-clip --no-show

# Shared domain modules (configurations, documents, runs, schema helpers)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/shared/configurations \
  --dir apps/ade-web/src/shared/builds \
  --dir apps/ade-web/src/shared/runs \
  apps/ade-web/src/shared/documents.ts \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-shared-domain.md" \
  --no-clip --no-show

# UI primitives and shared components
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/ui \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-ui.md" \
  --no-clip --no-show

# Workspace shell (nav + layout) and workspace directory
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/components \
  apps/ade-web/src/screens/Workspace/index.tsx \
  --dir apps/ade-web/src/screens/Workspaces \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-workspace-shell.md" \
  --no-clip --no-show

# Workspace sections (Documents)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/sections/Documents \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-documents.md" \
  --no-clip --no-show

# Workspace sections (Runs)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/sections/Runs \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-runs.md" \
  --no-clip --no-show

# Workspace sections (Overview)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/sections/Overview \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-overview.md" \
  --no-clip --no-show

# Workspace sections (Settings)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/sections/Settings \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-settings.md" \
  --no-clip --no-show

# Configuration Builder (list/detail screens)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-config-builder-detail.md" \
  --no-clip --no-show

# Configuration Builder workbench (core + components + state)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-config-builder-workbench.md" \
  --no-clip --no-show
