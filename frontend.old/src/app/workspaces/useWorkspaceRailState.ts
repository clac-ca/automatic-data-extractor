import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "../../shared/lib/storage";

interface WorkspaceRailStoredState {
  readonly pinned: string[];
  readonly collapsed: boolean;
}

const defaultState: WorkspaceRailStoredState = { pinned: [], collapsed: false };

export interface WorkspaceRailState {
  readonly pinnedDocumentIds: readonly string[];
  readonly isCollapsed: boolean;
  readonly toggleCollapse: () => void;
  readonly setCollapsed: (next: boolean) => void;
  readonly setPinned: (documentId: string, nextPinned: boolean) => void;
}

export function useWorkspaceRailState(workspaceId: string): WorkspaceRailState {
  const storage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspaceId}.rail_state`),
    [workspaceId],
  );

  const [state, setState] = useState<WorkspaceRailStoredState>(() => {
    const stored = storage.get<WorkspaceRailStoredState>();
    return stored ?? defaultState;
  });

  useEffect(() => {
    const stored = storage.get<WorkspaceRailStoredState>();
    setState(stored ?? defaultState);
  }, [storage]);

  useEffect(() => {
    storage.set(state);
  }, [state, storage]);

  const toggleCollapse = useCallback(() => {
    setState((current) => ({ ...current, collapsed: !current.collapsed }));
  }, []);

  const setCollapsed = useCallback((next: boolean) => {
    setState((current) => ({ ...current, collapsed: next }));
  }, []);

  const setPinned = useCallback((documentId: string, nextPinned: boolean) => {
    setState((current) => {
      const pinned = new Set(current.pinned);
      if (nextPinned) {
        pinned.add(documentId);
      } else {
        pinned.delete(documentId);
      }
      return { ...current, pinned: Array.from(pinned) };
    });
  }, []);

  return {
    pinnedDocumentIds: state.pinned,
    isCollapsed: state.collapsed,
    toggleCollapse,
    setCollapsed,
    setPinned,
  };
}
