import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@app/providers/AuthProvider";

import { createApiClient } from "../client";
import type { WorkspaceContext, WorkspaceProfile } from "../schemas/workspaces";

const MOCK_WORKSPACES: WorkspaceProfile[] = [
  {
    workspace_id: "wrk_default",
    name: "Demo Workspace",
    slug: "demo-workspace",
    role: "owner",
    permissions: ["documents:read", "jobs:read", "configurations:write"],
    is_default: true,
  },
  {
    workspace_id: "wrk_collab",
    name: "Research Team",
    slug: "research-team",
    role: "member",
    permissions: ["documents:read"],
    is_default: false,
  },
];

function createMockWorkspaceContext(workspaceId?: string): WorkspaceContext {
  const fallback = MOCK_WORKSPACES[0];
  const workspace = MOCK_WORKSPACES.find((entry) => entry.workspace_id === workspaceId) ?? fallback;
  return { workspace };
}

export function useWorkspacesQuery() {
  const { token } = useAuth();

  return useQuery<WorkspaceProfile[]>({
    queryKey: ["workspaces"],
    queryFn: async () => {
      const client = createApiClient(token);

      try {
        const response = await client.get<WorkspaceProfile[]>("/workspaces");
        if (Array.isArray(response) && response.length > 0) {
          return response;
        }
      } catch (error) {
        console.warn("Falling back to mock workspaces", error);
      }

      return MOCK_WORKSPACES;
    },
    staleTime: 60_000,
  });
}

export function useWorkspaceContextQuery(workspaceId?: string) {
  const { token } = useAuth();

  return useQuery<WorkspaceContext>({
    queryKey: ["workspaces", workspaceId],
    enabled: Boolean(workspaceId),
    queryFn: async () => {
      if (!workspaceId) {
        return createMockWorkspaceContext();
      }

      const client = createApiClient(token);

      try {
        return await client.get<WorkspaceContext>(`/workspaces/${workspaceId}`);
      } catch (error) {
        console.warn("Falling back to mock workspace context", error);
        return createMockWorkspaceContext(workspaceId);
      }
    },
    staleTime: 60_000,
  });
}
