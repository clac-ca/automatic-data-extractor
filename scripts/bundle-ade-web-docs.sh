#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

# Refresh ADE web bundles. Assumes .venv is present at repo root.
source .venv/bin/activate

generated_dir="apps/ade-web/.generated"
mkdir -p "${generated_dir}"

# Config Builder logic bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/app/App.tsx \
  apps/ade-web/src/app/AppProviders.tsx \
  apps/ade-web/src/app/nav/Link.tsx \
  apps/ade-web/src/app/nav/history.tsx \
  apps/ade-web/src/app/nav/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/types.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts \
  apps/ade-web/vite.config.ts \
  apps/ade-web/vitest.config.ts \
  --out "${generated_dir}/bundle-config-builder-logic.md" \
  --no-clip --show

# Config Builder UI bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/app/App.tsx \
  apps/ade-web/src/app/AppProviders.tsx \
  apps/ade-web/src/app/nav/Link.tsx \
  apps/ade-web/src/app/nav/history.tsx \
  apps/ade-web/src/app/nav/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Inspector.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx \
  apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/index.tsx \
  apps/ade-web/vite.config.ts \
  apps/ade-web/vitest.config.ts \
  --out "${generated_dir}/bundle-config-builder-ui.md" \
  --no-clip --show

# Shared data layer bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/app/App.tsx \
  apps/ade-web/src/app/AppProviders.tsx \
  apps/ade-web/src/app/nav/Link.tsx \
  apps/ade-web/src/app/nav/history.tsx \
  apps/ade-web/src/app/nav/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/shared/api/client.ts \
  apps/ade-web/src/shared/api/csrf.ts \
  apps/ade-web/src/shared/api/ndjson.ts \
  apps/ade-web/src/shared/api/pagination.ts \
  apps/ade-web/src/shared/auth/api.ts \
  apps/ade-web/src/shared/auth/api/logout.ts \
  apps/ade-web/src/shared/auth/hooks/useAuthProvidersQuery.ts \
  --out "${generated_dir}/bundle-shared-data.md" \
  --no-clip --show

# UI + editor primitives bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/app/App.tsx \
  apps/ade-web/src/app/AppProviders.tsx \
  apps/ade-web/src/app/nav/Link.tsx \
  apps/ade-web/src/app/nav/history.tsx \
  apps/ade-web/src/app/nav/urlState.ts \
  apps/ade-web/src/app/shell/GlobalSearchField.tsx \
  apps/ade-web/src/app/shell/GlobalTopBar.tsx \
  apps/ade-web/src/app/shell/ProfileDropdown.tsx \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/ui/Alert/Alert.tsx \
  apps/ade-web/src/ui/Alert/index.ts \
  apps/ade-web/src/ui/Avatar/Avatar.tsx \
  apps/ade-web/src/ui/Avatar/index.ts \
  --out "${generated_dir}/bundle-ui-and-editor.md" \
  --no-clip --show

# Workspace sections bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/app/App.tsx \
  apps/ade-web/src/app/AppProviders.tsx \
  apps/ade-web/src/app/nav/Link.tsx \
  apps/ade-web/src/app/nav/history.tsx \
  apps/ade-web/src/app/nav/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/screens/Workspace/sections/Documents/components/DocumentDetail.tsx \
  apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx \
  apps/ade-web/src/screens/Workspace/sections/Runs/index.tsx \
  apps/ade-web/src/screens/Workspace/sections/Overview/index.tsx \
  apps/ade-web/src/screens/Workspace/sections/Settings/components/SafeModeControls.tsx \
  apps/ade-web/src/screens/Workspace/sections/Settings/components/WorkspaceMembersSection.tsx \
  apps/ade-web/src/screens/Workspace/sections/Settings/components/WorkspaceRolesSection.tsx \
  --out "${generated_dir}/bundle-workspace-sections.md" \
  --no-clip --show

# Workspace shell bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/app/App.tsx \
  apps/ade-web/src/app/AppProviders.tsx \
  apps/ade-web/src/app/nav/Link.tsx \
  apps/ade-web/src/app/nav/history.tsx \
  apps/ade-web/src/app/nav/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/screens/Workspace/components/WorkspaceNav.tsx \
  apps/ade-web/src/screens/Workspace/components/workspace-navigation.tsx \
  apps/ade-web/src/screens/Workspace/index.tsx \
  apps/ade-web/src/screens/Workspaces/New/hooks/useCreateWorkspaceMutation.ts \
  apps/ade-web/src/screens/Workspaces/New/index.tsx \
  apps/ade-web/src/screens/Workspaces/components/WorkspaceDirectoryLayout.tsx \
  apps/ade-web/src/screens/Workspaces/index.tsx \
  --out "${generated_dir}/bundle-workspace-shell.md" \
  --no-clip --show

# ADE web docs bundle
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/docs \
  --ext md \
  --out "${generated_dir}/ade-web-docs-bundle.md" \
  --no-clip --no-show
