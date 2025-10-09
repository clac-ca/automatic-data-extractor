import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createGlobalRole, deleteRole, updateRole } from "../api";
import { adminKeys } from "./adminKeys";
import type { RoleCreatePayload, RoleDefinition, RoleUpdatePayload } from "../../../shared/api/types";

export function useCreateGlobalRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoleCreatePayload) => createGlobalRole(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.globalRoles() });
    },
  });
}

export function useUpdateRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ roleId, payload }: { roleId: string; payload: RoleUpdatePayload }) =>
      updateRole(roleId, payload),
    onSuccess: (_data: RoleDefinition) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.globalRoles() });
    },
  });
}

export function useDeleteRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (roleId: string) => deleteRole(roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.globalRoles() });
      queryClient.invalidateQueries({ queryKey: adminKeys.globalAssignments() });
    },
  });
}
