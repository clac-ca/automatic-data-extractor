import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaces } from "../api";
import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import { workspacesKeys } from "./keys";

export interface WorkspacesQueryOptions {
  readonly enabled?: boolean;
}

export function workspacesListQueryOptions(options: WorkspacesQueryOptions = {}) {
  return {
    queryKey: workspacesKeys.list(),
    queryFn: ({ signal }: { signal?: AbortSignal }) => fetchWorkspaces(signal),
    staleTime: 60_000,
    enabled: options.enabled ?? true,
  };
}

export function useWorkspacesQuery(options: WorkspacesQueryOptions = {}) {
  return useQuery<WorkspaceProfile[]>(workspacesListQueryOptions(options));
}
