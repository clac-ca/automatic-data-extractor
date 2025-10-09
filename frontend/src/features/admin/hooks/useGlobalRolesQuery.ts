import { useQuery } from "@tanstack/react-query";

import { fetchGlobalRoles } from "../api";
import { adminKeys } from "./adminKeys";
import type { RoleDefinition } from "../../../shared/api/types";

export function useGlobalRolesQuery() {
  return useQuery<RoleDefinition[]>({
    queryKey: adminKeys.globalRoles(),
    queryFn: fetchGlobalRoles,
    staleTime: 60_000,
  });
}
