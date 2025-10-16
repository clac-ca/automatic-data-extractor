import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceDocuments, type DocumentsQueryParams } from "../api";
import type { DocumentListResponse } from "../../../shared/types/documents";

export const documentKeys = {
  all: ["documents"] as const,
  lists: (workspaceId: string) => [...documentKeys.all, workspaceId, "list"] as const,
  list: (workspaceId: string, params: DocumentsQueryParams) => [
    ...documentKeys.lists(workspaceId),
    params,
  ] as const,
};

export function useDocumentsQuery(workspaceId: string, params: DocumentsQueryParams) {
  return useQuery<DocumentListResponse>({
    queryKey: documentKeys.list(workspaceId, params),
    queryFn: ({ signal }) => fetchWorkspaceDocuments(workspaceId, params, signal),
    enabled: workspaceId.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}
