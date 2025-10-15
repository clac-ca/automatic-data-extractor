import type { WorkspaceProfile } from "../types/workspaces";
import { createScopedStorage } from "./storage";

const STORAGE_KEY = "ade.active_workspace";
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
