const UI_STORAGE_PREFIX = "ade.ui";

export const uiStorageKeys = {
  sidebarPinned: `${UI_STORAGE_PREFIX}.sidebar.pinned`,
  themeMode: `${UI_STORAGE_PREFIX}.theme.mode`,
  themeName: `${UI_STORAGE_PREFIX}.theme.name`,
  workspaceLastActive: `${UI_STORAGE_PREFIX}.workspace.lastActive`,
  documentsCursor: (workspaceId: string) => `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.documents.cursor`,
  documentsLastView: (workspaceId: string) => `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.documents.lastView`,
  documentsTableColumnSizing: (workspaceId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.documents.table.columnSizing`,
  documentsPreviewPaneHeight: (workspaceId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.documents.preview.height`,
  workbenchTabs: (workspaceId: string, configId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.config.${configId}.workbench.tabs`,
  workbenchConsole: (workspaceId: string, configId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.config.${configId}.workbench.console`,
  workbenchExplorerExpanded: (workspaceId: string, configId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.config.${configId}.workbench.explorer.expanded`,
  workbenchLayout: (workspaceId: string, configId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.config.${configId}.workbench.layout`,
  workbenchConsoleLevelFilter: `${UI_STORAGE_PREFIX}.workbench.console.levelFilter`,
  workbenchGuidedTourSeen: (workspaceId: string) =>
    `${UI_STORAGE_PREFIX}.workspace.${workspaceId}.workbench.guidedTour.seen`,
};
