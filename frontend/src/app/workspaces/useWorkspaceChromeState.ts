import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "../../shared/lib/storage";

interface WorkspaceChromeStoredState {
  readonly navCollapsed: boolean;
  readonly sectionCollapsed: boolean;
  readonly focusMode: boolean;
}

const defaultState: WorkspaceChromeStoredState = {
  navCollapsed: false,
  sectionCollapsed: false,
  focusMode: false,
};

export interface WorkspaceChromeState {
  readonly isNavCollapsed: boolean;
  readonly toggleNavCollapsed: () => void;
  readonly setNavCollapsed: (next: boolean) => void;
  readonly isSectionCollapsed: boolean;
  readonly toggleSectionCollapsed: () => void;
  readonly setSectionCollapsed: (next: boolean) => void;
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
    return { ...defaultState, ...(stored ?? {}) };
  });

  useEffect(() => {
    const stored = storage.get<WorkspaceChromeStoredState>();
    setState({ ...defaultState, ...(stored ?? {}) });
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

  const toggleSectionCollapsed = useCallback(() => {
    setState((current) => ({ ...current, sectionCollapsed: !current.sectionCollapsed }));
  }, []);

  const setSectionCollapsed = useCallback((next: boolean) => {
    setState((current) => ({ ...current, sectionCollapsed: next }));
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
    isSectionCollapsed: state.sectionCollapsed,
    toggleSectionCollapsed,
    setSectionCollapsed,
    isFocusMode: state.focusMode,
    toggleFocusMode,
    setFocusMode,
  };
}
