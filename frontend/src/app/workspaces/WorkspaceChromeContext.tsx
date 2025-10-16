/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface InspectorOptions {
  readonly title?: string;
  readonly content: ReactNode;
  readonly onClose?: () => void;
}

interface WorkspaceChromeContextValue {
  readonly isNavCollapsed: boolean;
  readonly toggleNavCollapsed: () => void;
  readonly setNavCollapsed: (next: boolean) => void;
  readonly isFocusMode: boolean;
  readonly toggleFocusMode: () => void;
  readonly setFocusMode: (next: boolean) => void;
  readonly inspector: {
    readonly isOpen: boolean;
    readonly title?: string;
    readonly content: ReactNode | null;
  };
  readonly openInspector: (options: InspectorOptions) => void;
  readonly closeInspector: () => void;
}

const WorkspaceChromeContext = createContext<WorkspaceChromeContextValue | undefined>(undefined);

export interface WorkspaceChromeProviderProps {
  readonly isNavCollapsed: boolean;
  readonly toggleNavCollapsed: () => void;
  readonly setNavCollapsed: (next: boolean) => void;
  readonly isFocusMode: boolean;
  readonly toggleFocusMode: () => void;
  readonly setFocusMode: (next: boolean) => void;
  readonly children: ReactNode;
}

export function WorkspaceChromeProvider({
  isNavCollapsed,
  toggleNavCollapsed,
  setNavCollapsed,
  isFocusMode,
  toggleFocusMode,
  setFocusMode,
  children,
}: WorkspaceChromeProviderProps) {
  const [inspector, setInspector] = useState<{ title?: string; content: ReactNode | null }>({
    title: undefined,
    content: null,
  });
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const inspectorCleanupRef = useRef<(() => void) | undefined>(undefined);

  const openInspector = useCallback((options: InspectorOptions) => {
    setInspector({ title: options.title, content: options.content });
    setInspectorOpen(true);
    inspectorCleanupRef.current = options.onClose;
  }, []);

  const closeInspector = useCallback(() => {
    setInspector((current) => ({ ...current, content: null }));
    setInspectorOpen(false);
    const cleanup = inspectorCleanupRef.current;
    inspectorCleanupRef.current = undefined;
    if (cleanup) {
      cleanup();
    }
  }, []);

  const value = useMemo<WorkspaceChromeContextValue>(
    () => ({
      isNavCollapsed,
      toggleNavCollapsed,
      setNavCollapsed,
      isFocusMode,
      toggleFocusMode,
      setFocusMode,
      inspector: {
        isOpen: inspectorOpen,
        title: inspector.title,
        content: inspector.content,
      },
      openInspector,
      closeInspector,
    }),
    [
      closeInspector,
      inspector.content,
      inspector.title,
      inspectorOpen,
      isFocusMode,
      isNavCollapsed,
      openInspector,
      setFocusMode,
      setNavCollapsed,
      toggleFocusMode,
      toggleNavCollapsed,
    ],
  );

  return <WorkspaceChromeContext.Provider value={value}>{children}</WorkspaceChromeContext.Provider>;
}

export function useWorkspaceChrome() {
  const context = useContext(WorkspaceChromeContext);
  if (!context) {
    throw new Error("useWorkspaceChrome must be used within WorkspaceChromeProvider");
  }
  return context;
}
