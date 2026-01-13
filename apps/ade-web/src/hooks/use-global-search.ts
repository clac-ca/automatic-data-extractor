import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceDocuments, type DocumentListRow } from "@api/documents";
import { fetchWorkspaceRuns, type RunResource } from "@api/runs/api";
import { fetchWorkspaces } from "@api/workspaces/api";
import type { WorkspaceProfile } from "@schema/workspaces";

export const GLOBAL_SEARCH_TRIGGER_LENGTH = 2;
export const GLOBAL_SEARCH_RESULT_LIMIT = 5;
export const GLOBAL_SEARCH_DOCUMENT_SORT = '[{"id":"createdAt","desc":true}]';
export const GLOBAL_SEARCH_RUN_SORT = '[{"id":"createdAt","desc":true}]';

export type GlobalSearchScope =
  | {
      readonly kind: "workspace";
      readonly workspaceId: string;
    }
  | {
      readonly kind: "directory";
    };

interface UseGlobalSearchDataOptions {
  readonly scope: GlobalSearchScope;
  readonly query: string;
  readonly enabled: boolean;
}

export function useGlobalSearchData({ scope, query, enabled }: UseGlobalSearchDataOptions) {
  const normalizedQuery = query.trim();
  const shouldSearch = normalizedQuery.length >= GLOBAL_SEARCH_TRIGGER_LENGTH;
  const workspaceId = scope.kind === "workspace" ? scope.workspaceId : "";

  const documentsQuery = useQuery({
    queryKey: ["global-search", "documents", workspaceId, normalizedQuery],
    queryFn: ({ signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort: GLOBAL_SEARCH_DOCUMENT_SORT,
          limit: GLOBAL_SEARCH_RESULT_LIMIT,
          q: normalizedQuery,
        },
        signal,
      ),
    enabled: enabled && scope.kind === "workspace" && shouldSearch,
    staleTime: 20_000,
  });

  const runsQuery = useQuery({
    queryKey: ["global-search", "runs", workspaceId, normalizedQuery],
    queryFn: ({ signal }) =>
      fetchWorkspaceRuns(
        workspaceId,
        {
          limit: GLOBAL_SEARCH_RESULT_LIMIT,
          sort: GLOBAL_SEARCH_RUN_SORT,
          q: normalizedQuery,
        },
        signal,
      ),
    enabled: enabled && scope.kind === "workspace" && shouldSearch,
    staleTime: 20_000,
  });

  const workspacesQuery = useQuery({
    queryKey: ["global-search", "workspaces", normalizedQuery],
    queryFn: ({ signal }) =>
      fetchWorkspaces({ limit: GLOBAL_SEARCH_RESULT_LIMIT, q: normalizedQuery, signal }),
    enabled: enabled && scope.kind === "directory" && shouldSearch,
    staleTime: 30_000,
  });

  const documents = (documentsQuery.data?.items ?? []) as DocumentListRow[];
  const runs = (runsQuery.data?.items ?? []) as RunResource[];
  const workspaces = (workspacesQuery.data?.items ?? []) as WorkspaceProfile[];
  const isFetching = documentsQuery.isFetching || runsQuery.isFetching || workspacesQuery.isFetching;
  const isError = documentsQuery.isError || runsQuery.isError || workspacesQuery.isError;

  return {
    documents,
    runs,
    workspaces,
    isFetching,
    isError,
  };
}
