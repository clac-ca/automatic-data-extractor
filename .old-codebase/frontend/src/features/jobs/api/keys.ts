export const jobsKeys = {
  root: (workspaceId: string) => ["workspaces", workspaceId, "jobs"] as const,
  list: (workspaceId: string, status: string | null = null, inputDocumentId: string | null = null, limit: number | null = null, offset: number | null = null) =>
    [
      ...jobsKeys.root(workspaceId),
      "list",
      status,
      inputDocumentId,
      limit,
      offset,
    ] as const,
  document: (workspaceId: string, documentId: string, limit: number | null = null) =>
    [...jobsKeys.root(workspaceId), "document", documentId, limit] as const,
  detail: (workspaceId: string, jobId: string) =>
    [...jobsKeys.root(workspaceId), "detail", jobId] as const,
};
