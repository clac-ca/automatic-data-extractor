import { useQuery, type QueryFunctionContext } from "@tanstack/react-query";

import {
  listWorkspaceDocuments,
  normaliseStatusFilter,
  type StatusFilterInput,
} from "./client";
import type { DocumentListResponse, DocumentStatus } from "../../../shared/types/documents";
import { documentsKeys } from "./keys";

export type DocumentsStatusFilter = "all" | DocumentStatus | readonly DocumentStatus[];

export interface WorkspaceDocumentsQueryOptions {
  readonly status?: DocumentsStatusFilter;
  readonly search?: string | null;
  readonly sort?: string | null;
}

export function workspaceDocumentsQueryOptions(
  workspaceId: string,
  options: WorkspaceDocumentsQueryOptions = {},
) {
  const rawStatus = options.status === "all" ? undefined : (options.status as StatusFilterInput);
  const resolvedStatus = normaliseStatusFilter(rawStatus) ?? null;
  const search = options.search?.trim() ?? null;
  const sort = options.sort?.trim() ?? null;

  return {
    queryKey: documentsKeys.list(workspaceId, resolvedStatus, search, sort),
    queryFn: ({ signal }: QueryFunctionContext) =>
      listWorkspaceDocuments(
        workspaceId,
        { status: resolvedStatus ?? undefined, search, sort },
        signal,
      ),
    enabled: workspaceId.length > 0,
    placeholderData: (previous: DocumentListResponse | undefined) => previous,
    staleTime: 15_000,
  };
}

export function useWorkspaceDocumentsQuery(
  workspaceId: string,
  options: WorkspaceDocumentsQueryOptions = {},
) {
  return useQuery<DocumentListResponse>(workspaceDocumentsQueryOptions(workspaceId, options));
}
