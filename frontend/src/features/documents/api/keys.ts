import type { DocumentStatus } from "../../../shared/types/documents";

export const documentsKeys = {
  all: () => ["documents"] as const,
  workspace: (workspaceId: string) => [...documentsKeys.all(), workspaceId] as const,
  list: (
    workspaceId: string,
    status: readonly DocumentStatus[] | null,
    search: string | null,
    sort: string | null,
  ) => [
    ...documentsKeys.workspace(workspaceId),
    "list",
    { status, search, sort },
  ] as const,
};
