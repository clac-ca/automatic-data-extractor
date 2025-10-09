import { useQuery } from "@tanstack/react-query";

import { fetchGlobalRoleAssignments } from "../api";
import { adminKeys } from "./adminKeys";
import type { RoleAssignment } from "../../../shared/api/types";

export function useGlobalAssignmentsQuery(filters?: { principal_id?: string; role_id?: string }) {
  return useQuery<RoleAssignment[]>({
    queryKey: adminKeys.globalAssignments(filters),
    queryFn: () => fetchGlobalRoleAssignments(filters ?? {}),
    staleTime: 30_000,
  });
}
