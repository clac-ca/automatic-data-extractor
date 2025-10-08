export const queryKeys = {
  session: ['auth', 'session'] as const,
  setupStatus: ['setup', 'status'] as const,
  providers: ['auth', 'providers'] as const,
  workspaces: ['workspaces'] as const,
  workspace: (workspaceId: string) => ['workspaces', workspaceId] as const,
  documentTypes: (workspaceId: string) =>
    ['workspaces', workspaceId, 'document-types'] as const,
  documentType: (workspaceId: string, documentTypeId: string) =>
    ['workspaces', workspaceId, 'document-types', documentTypeId] as const,
  configuration: (configurationId: string) =>
    ['configurations', configurationId] as const,
} as const
