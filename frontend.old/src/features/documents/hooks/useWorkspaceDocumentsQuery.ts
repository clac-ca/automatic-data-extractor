import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceDocuments } from "../api";

export const documentKeys = {
  all: ["documents"] as const,
  list: (workspaceId: string) => [...documentKeys.all, workspaceId, "list"] as const,
};

export function useWorkspaceDocumentsQuery(workspaceId: string) {
  return useQuery({
    queryKey: documentKeys.list(workspaceId),
    queryFn: ({ signal }) => fetchWorkspaceDocuments(workspaceId, signal),
    enabled: workspaceId.length > 0,
    staleTime: 30_000,
  });
}
