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
  apps/ade-web/src/App.tsx \
  apps/ade-web/src/components/providers/AppProviders.tsx \
  apps/ade-web/src/navigation/Link.tsx \
  apps/ade-web/src/navigation/history.tsx \
  apps/ade-web/src/navigation/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/types.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/utils/console.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts \
  apps/ade-web/vite.config.ts \
  apps/ade-web/vitest.config.ts \
  --out "${generated_dir}/bundle-config-builder-logic.md" \
  --show

# Config Builder UI bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/App.tsx \
  apps/ade-web/src/components/providers/AppProviders.tsx \
  apps/ade-web/src/navigation/Link.tsx \
  apps/ade-web/src/navigation/history.tsx \
  apps/ade-web/src/navigation/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/detail/index.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/Inspector.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx \
  apps/ade-web/src/pages/Workspace/sections/ConfigBuilder/workbench/index.tsx \
  apps/ade-web/vite.config.ts \
  apps/ade-web/vitest.config.ts \
  --out "${generated_dir}/bundle-config-builder-ui.md" \
  --show

# Shared data layer bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/App.tsx \
  apps/ade-web/src/components/providers/AppProviders.tsx \
  apps/ade-web/src/navigation/Link.tsx \
  apps/ade-web/src/navigation/history.tsx \
  apps/ade-web/src/navigation/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/api/client.ts \
  apps/ade-web/src/api/csrf.ts \
  apps/ade-web/src/api/ndjson.ts \
  apps/ade-web/src/api/pagination.ts \
  apps/ade-web/src/api/auth/api.ts \
  apps/ade-web/src/hooks/auth/useAuthProvidersQuery.ts \
  --out "${generated_dir}/bundle-shared-data.md" \
  --show

# UI + editor primitives bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/App.tsx \
  apps/ade-web/src/components/providers/AppProviders.tsx \
  apps/ade-web/src/navigation/Link.tsx \
  apps/ade-web/src/navigation/history.tsx \
  apps/ade-web/src/navigation/urlState.ts \
  apps/ade-web/src/components/shell/GlobalSearchField.tsx \
  apps/ade-web/src/components/shell/GlobalTopBar.tsx \
  apps/ade-web/src/components/shell/ProfileDropdown.tsx \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/components/ui/alert/Alert.tsx \
  apps/ade-web/src/components/ui/alert/index.ts \
  apps/ade-web/src/components/ui/avatar/Avatar.tsx \
  apps/ade-web/src/components/ui/avatar/index.ts \
  --out "${generated_dir}/bundle-ui-and-editor.md" \
  --show

# Workspace sections bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/App.tsx \
  apps/ade-web/src/components/providers/AppProviders.tsx \
  apps/ade-web/src/navigation/Link.tsx \
  apps/ade-web/src/navigation/history.tsx \
  apps/ade-web/src/navigation/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/pages/Workspace/sections/Documents/components/DocumentDetail.tsx \
  apps/ade-web/src/pages/Workspace/sections/Documents/index.tsx \
  apps/ade-web/src/pages/Workspace/sections/Runs/index.tsx \
  apps/ade-web/src/pages/Workspace/sections/Overview/index.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/WorkspaceSettingsRoute.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/components/SettingsLayout.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/components/SettingsDrawer.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/components/SettingsSectionHeader.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/components/SaveBar.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/components/ConfirmDialog.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/components/UnsavedChangesPrompt.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/sectionContext.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/pages/GeneralSettingsPage.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/pages/RolesSettingsPage.tsx \
  apps/ade-web/src/pages/Workspace/sections/Settings/pages/DangerSettingsPage.tsx \
  --out "${generated_dir}/bundle-workspace-sections.md" \
  --show

# Workspace shell bundle
ade bundle apps/ade-web/README.md \
  apps/ade-web/src/App.tsx \
  apps/ade-web/src/components/providers/AppProviders.tsx \
  apps/ade-web/src/navigation/Link.tsx \
  apps/ade-web/src/navigation/history.tsx \
  apps/ade-web/src/navigation/urlState.ts \
  apps/ade-web/src/main.tsx \
  apps/ade-web/src/pages/Workspace/components/WorkspaceNav.tsx \
  apps/ade-web/src/pages/Workspace/components/workspace-navigation.tsx \
  apps/ade-web/src/pages/Workspace/index.tsx \
  apps/ade-web/src/hooks/workspaces/useCreateWorkspaceMutation.ts \
  apps/ade-web/src/pages/Workspaces/New/index.tsx \
  apps/ade-web/src/pages/Workspaces/components/WorkspaceDirectoryLayout.tsx \
  apps/ade-web/src/pages/Workspaces/index.tsx \
  --out "${generated_dir}/bundle-workspace-shell.md" \
  --show

# ADE web docs bundle
ade bundle apps/ade-web/README.md \
  --dir apps/ade-web/docs \
  --ext md \
  --out "${generated_dir}/ade-web-docs-bundle.md" \
  --no-show
