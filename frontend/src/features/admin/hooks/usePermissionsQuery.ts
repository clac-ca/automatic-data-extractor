import { useQuery } from "@tanstack/react-query";

import { fetchPermissions } from "../api";
import { adminKeys } from "./adminKeys";
import type { PermissionDefinition } from "../../../shared/api/types";

export function usePermissionsQuery() {
  return useQuery<PermissionDefinition[]>({
    queryKey: adminKeys.permissions(),
    queryFn: fetchPermissions,
    staleTime: 5 * 60_000,
  });
}
