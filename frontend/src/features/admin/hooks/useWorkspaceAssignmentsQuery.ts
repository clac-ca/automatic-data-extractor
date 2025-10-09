import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceRoleAssignments } from "../api";
import { adminKeys } from "./adminKeys";
import type { RoleAssignment } from "../../../shared/api/types";

export function useWorkspaceAssignmentsQuery(
  workspaceId: string,
  filters?: { principal_id?: string; role_id?: string },
) {
  return useQuery<RoleAssignment[]>({
    queryKey: adminKeys.workspaceAssignments(workspaceId, filters),
    queryFn: () => fetchWorkspaceRoleAssignments(workspaceId, filters ?? {}),
    enabled: workspaceId.trim().length > 0,
    staleTime: 30_000,
  });
}
