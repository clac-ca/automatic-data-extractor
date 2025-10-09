import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaces } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type { WorkspaceProfile } from "../../../shared/api/types";

export function useWorkspacesQuery() {
  return useQuery<WorkspaceProfile[]>({
    queryKey: workspaceKeys.lists(),
    queryFn: ({ signal }) => fetchWorkspaces({ signal }),
    staleTime: 30_000,
  });
}
