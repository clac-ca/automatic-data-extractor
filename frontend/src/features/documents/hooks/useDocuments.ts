import { useQuery } from "@tanstack/react-query";

import { listWorkspaceDocuments, normaliseStatusFilter, type StatusFilterInput } from "../api";
import type { DocumentListResponse, DocumentStatus } from "../../../shared/types/documents";

export type DocumentsStatusFilter = "all" | DocumentStatus | readonly DocumentStatus[];

export const documentsQueryKeys = {
  all: ["documents"] as const,
  lists: (workspaceId: string) => [...documentsQueryKeys.all, workspaceId, "list"] as const,
  list: (
    workspaceId: string,
    status: readonly DocumentStatus[] | null,
    search: string | null,
    sort: string | null,
  ) => [
    ...documentsQueryKeys.lists(workspaceId),
    { status, search, sort },
  ] as const,
};

export interface DocumentsQueryOptions {
  readonly status?: DocumentsStatusFilter;
  readonly search?: string | null;
  readonly sort?: string | null;
}

export function useDocuments(workspaceId: string, options: DocumentsQueryOptions = {}) {
  const rawStatus = options.status === "all" ? undefined : (options.status as StatusFilterInput);
  const resolvedStatus = normaliseStatusFilter(rawStatus) ?? null;
  const search = options.search?.trim() ?? null;
  const sort = options.sort?.trim() ?? null;

  return useQuery<DocumentListResponse>({
    queryKey: documentsQueryKeys.list(workspaceId, resolvedStatus, search, sort),
    queryFn: ({ signal }) =>
      listWorkspaceDocuments(
        workspaceId,
        { status: resolvedStatus ?? undefined, search, sort },
        signal,
      ),
    enabled: workspaceId.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 15_000,
  });
}
