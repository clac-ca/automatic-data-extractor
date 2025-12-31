import { createScopedStorage } from "@utils/storage";

const PREFERRED_WORKSPACE_STORAGE_KEY = "backend.app.active_workspace";
const storage = createScopedStorage(PREFERRED_WORKSPACE_STORAGE_KEY);

export function readPreferredWorkspaceId(): string | null {
  return storage.get<string>();
}

export function writePreferredWorkspaceId(workspaceId: string | null): void {
  if (!workspaceId) {
    storage.clear();
    return;
  }
  storage.set(workspaceId);
}
