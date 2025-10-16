import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "../../shared/lib/storage";

interface WorkspaceChromeStoredState {
  readonly navCollapsed: boolean;
  readonly focusMode: boolean;
}

const defaultState: WorkspaceChromeStoredState = {
  navCollapsed: false,
  focusMode: false,
};

export interface WorkspaceChromeState {
  readonly isNavCollapsed: boolean;
  readonly toggleNavCollapsed: () => void;
  readonly setNavCollapsed: (next: boolean) => void;
  readonly isFocusMode: boolean;
  readonly toggleFocusMode: () => void;
  readonly setFocusMode: (next: boolean) => void;
}

export function useWorkspaceChromeState(workspaceId: string): WorkspaceChromeState {
  const storage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspaceId}.chrome_state`),
    [workspaceId],
  );

  const [state, setState] = useState<WorkspaceChromeStoredState>(() => {
    const stored = storage.get<WorkspaceChromeStoredState>();
    return stored ?? defaultState;
  });

  useEffect(() => {
    const stored = storage.get<WorkspaceChromeStoredState>();
    setState(stored ?? defaultState);
  }, [storage]);

  useEffect(() => {
    storage.set(state);
  }, [state, storage]);

  const toggleNavCollapsed = useCallback(() => {
    setState((current) => ({ ...current, navCollapsed: !current.navCollapsed }));
  }, []);

  const setNavCollapsed = useCallback((next: boolean) => {
    setState((current) => ({ ...current, navCollapsed: next }));
  }, []);

  const toggleFocusMode = useCallback(() => {
    setState((current) => ({ ...current, focusMode: !current.focusMode }));
  }, []);

  const setFocusMode = useCallback((next: boolean) => {
    setState((current) => ({ ...current, focusMode: next }));
  }, []);

  return {
    isNavCollapsed: state.navCollapsed,
    toggleNavCollapsed,
    setNavCollapsed,
    isFocusMode: state.focusMode,
    toggleFocusMode,
    setFocusMode,
  };
}
