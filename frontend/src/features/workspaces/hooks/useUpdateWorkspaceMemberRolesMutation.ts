import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateWorkspaceMemberRoles } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type {
  WorkspaceMember,
  WorkspaceMemberRolesUpdatePayload,
} from "../../../shared/api/types";

interface UpdateMemberRolesVariables {
  membershipId: string;
  payload: WorkspaceMemberRolesUpdatePayload;
}

export function useUpdateWorkspaceMemberRolesMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceMember, unknown, UpdateMemberRolesVariables>({
    mutationFn: ({ membershipId, payload }) => updateWorkspaceMemberRoles(workspaceId, membershipId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: workspaceKeys.members(workspaceId) });
    },
  });
}
