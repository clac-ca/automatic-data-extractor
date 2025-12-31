import { createScopedStorage } from "@utils/storage";

export type LastSelection = { readonly configId?: string | null } | null;

export const buildLastSelectionStorageKey = (workspaceId: string) =>
  `ade.ui.workspace.${workspaceId}.config-builder.last`;

export function createLastSelectionStorage(workspaceId: string) {
  return createScopedStorage(buildLastSelectionStorageKey(workspaceId));
}

export function persistLastSelection(
  storage: ReturnType<typeof createLastSelectionStorage>,
  configId: string | null,
): LastSelection {
  if (configId) {
    const payload: LastSelection = { configId };
    storage.set<LastSelection>(payload);
    return payload;
  }
  storage.clear();
  return null;
}
