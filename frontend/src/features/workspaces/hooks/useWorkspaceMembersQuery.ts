import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceMembers } from "../api";
import { workspaceKeys } from "./workspaceKeys";
import type { WorkspaceMember } from "../../../shared/api/types";

export function useWorkspaceMembersQuery(workspaceId: string, enabled: boolean = true) {
  return useQuery<WorkspaceMember[]>({
    queryKey: workspaceKeys.members(workspaceId),
    queryFn: ({ signal }) => fetchWorkspaceMembers(workspaceId, { signal }),
    enabled,
    staleTime: 15_000,
  });
}
