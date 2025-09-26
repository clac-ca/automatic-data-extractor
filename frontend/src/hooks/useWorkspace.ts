import { useWorkspaceContext } from "@app/providers/WorkspaceProvider";

export function useWorkspace() {
  return useWorkspaceContext();
}
