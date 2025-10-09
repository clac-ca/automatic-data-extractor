import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createGlobalRoleAssignment,
  createWorkspaceRoleAssignment,
  deleteRoleAssignment,
} from "../api";
import { adminKeys } from "./adminKeys";
import type { RoleAssignment, RoleAssignmentCreatePayload } from "../../../shared/api/types";

export function useCreateGlobalAssignmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoleAssignmentCreatePayload) => createGlobalRoleAssignment(payload),
    onSuccess: (_assignment: RoleAssignment) => {
      queryClient.invalidateQueries({ queryKey: adminKeys.globalAssignments() });
    },
  });
}

export function useDeleteGlobalAssignmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => deleteRoleAssignment(assignmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.globalAssignments() });
    },
  });
}

export function useCreateWorkspaceAssignmentMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoleAssignmentCreatePayload) =>
      createWorkspaceRoleAssignment(workspaceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.workspaceAssignments(workspaceId) });
    },
  });
}

export function useDeleteWorkspaceAssignmentMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => deleteRoleAssignment(assignmentId, workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.workspaceAssignments(workspaceId) });
    },
  });
}
