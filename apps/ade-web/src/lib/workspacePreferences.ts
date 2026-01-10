import { createScopedStorage } from "@lib/storage";
import { uiStorageKeys } from "@lib/uiStorageKeys";

const storage = createScopedStorage(uiStorageKeys.workspaceLastActive);

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
