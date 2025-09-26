import { useQuery } from "@tanstack/react-query";

import { listWorkspaces } from "@api/workspaces";
import { useApiClient } from "@hooks/useApiClient";

import type { WorkspaceQueryResult } from "@features/workspaces/types";

export function useWorkspacesQuery() {
  const client = useApiClient();

  return useQuery<WorkspaceQueryResult, Error>({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const workspaces = await listWorkspaces(client);
      const defaultWorkspace = workspaces.find((item) => item.isDefault) ?? null;
      return {
        workspaces,
        defaultWorkspaceId: defaultWorkspace?.workspaceId ?? null
      };
    }
  });
}
