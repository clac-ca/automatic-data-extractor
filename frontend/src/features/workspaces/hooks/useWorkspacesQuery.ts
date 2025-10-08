import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaces } from "../api";
import { workspaceKeys } from "./workspaceKeys";

export function useWorkspacesQuery() {
  return useQuery({
    queryKey: workspaceKeys.lists(),
    queryFn: fetchWorkspaces,
    staleTime: 30_000,
  });
}
