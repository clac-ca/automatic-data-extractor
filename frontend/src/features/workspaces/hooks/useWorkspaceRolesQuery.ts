import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceRoles } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type { WorkspaceRoleDefinition } from "../../../shared/api/types";

export function useWorkspaceRolesQuery(workspaceId: string, enabled: boolean = true) {
  return useQuery<WorkspaceRoleDefinition[]>({
    queryKey: workspaceKeys.roles(workspaceId),
    queryFn: ({ signal }) => fetchWorkspaceRoles(workspaceId, { signal }),
    enabled,
    staleTime: 60_000,
  });
}
