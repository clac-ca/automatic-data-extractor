#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

# Bundle ADE web source by logical areas.

generated_dir="apps/ade-web/.generated"
mkdir -p "${generated_dir}"

# App shell + navigation + bootstrap
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/app/layouts/AppShell.tsx \
  apps/ade-web/src/app/routes.tsx \
  apps/ade-web/src/app/router.tsx \
  apps/ade-web/src/providers/AppProviders.tsx \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-app.md" \
  --no-show

# Shared data layer (API clients)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/api \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-shared-api.md" \
  --no-show

# Shared auth + notifications + storage helpers
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/providers/auth \
  --dir apps/ade-web/src/providers/notifications \
  --dir apps/ade-web/src/providers/theme \
  apps/ade-web/src/lib/storage.ts \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-shared-core.md" \
  --no-show

# Shared domain modules (configurations, documents, runs, schema helpers)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/api/configurations \
  --dir apps/ade-web/src/api/documents \
  --dir apps/ade-web/src/api/runs \
  --dir apps/ade-web/src/types \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-shared-domain.md" \
  --no-show

# UI primitives and shared components
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/components \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-ui.md" \
  --no-show

# Workspace shell (nav + layout) and workspace directory
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/components \
  apps/ade-web/src/pages/Workspace/index.tsx \
  --dir apps/ade-web/src/pages/Workspaces \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-workspace-shell.md" \
  --no-show

# Workspace sections (Documents)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/Documents \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-documents.md" \
  --no-show

# Workspace sections (Runs)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/Runs \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-runs.md" \
  --no-show

# Workspace sections (Overview)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/Overview \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-overview.md" \
  --no-show

# Workspace sections (Settings)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/Settings \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-settings.md" \
  --no-show

# Configuration Builder (list/detail screens)
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/detail \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-config-builder-detail.md" \
  --no-show

# Configuration Builder workbench — chrome/root (overall layout + types)
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/index.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/types.ts \
  --out "${generated_dir}/ade-web-src-config-builder-workbench-chrome.md" \
  --no-show

# Configuration Builder workbench — editor/explorer/inspector surface
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/EditorPane.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx \
  --out "${generated_dir}/ade-web-src-config-builder-workbench-editor.md" \
  --no-show

# Configuration Builder workbench — console/bottom panel
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/consoleFormatting.tsx \
  --out "${generated_dir}/ade-web-src-config-builder-workbench-console.md" \
  --no-show

# Configuration Builder workbench — state/hooks
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/state \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-config-builder-workbench-state.md" \
  --no-show

# Configuration Builder workbench — utilities, defaults, seed data
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/utils \
  --dir apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/seed \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx \
  --ext ts --ext tsx --ext md \
  --out "${generated_dir}/ade-web-src-config-builder-workbench-support.md" \
  --no-show
