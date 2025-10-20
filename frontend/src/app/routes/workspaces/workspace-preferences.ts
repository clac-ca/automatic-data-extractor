import type { WorkspaceProfile } from "@schema/workspaces";
import { createScopedStorage } from "@shared/storage";

const STORAGE_KEY = "backend.app.active_workspace";
const storage = createScopedStorage(STORAGE_KEY);

export function readPreferredWorkspaceId(): string | null {
  return storage.get<string>();
}

export function writePreferredWorkspace(workspace: WorkspaceProfile | null): void {
  if (!workspace) {
    storage.clear();
    return;
  }
  storage.set(workspace.id);
}
