import { uiStorageKeys } from "@/lib/uiStorageKeys";

export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return uiStorageKeys.workbenchReturnPath(workspaceId);
}
