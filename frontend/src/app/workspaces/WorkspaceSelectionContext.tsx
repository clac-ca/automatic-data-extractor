import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

const STORAGE_KEY = "ade.workspace.selection";

interface WorkspaceSelectionContextValue {
  selectedWorkspaceId: string | null;
  setSelectedWorkspaceId: (workspaceId: string | null) => void;
}

const WorkspaceSelectionContext =
  createContext<WorkspaceSelectionContextValue | undefined>(undefined);

interface WorkspaceSelectionProviderProps {
  children: ReactNode;
}

function readInitialSelection(): string | null {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && stored.trim() ? stored : null;
}

export function WorkspaceSelectionProvider({
  children,
}: WorkspaceSelectionProviderProps) {
  const [selectedWorkspaceId, internalSetSelection] = useState<string | null>(
    readInitialSelection(),
  );

  const setSelectedWorkspaceId = useCallback((workspaceId: string | null) => {
    internalSetSelection(workspaceId);
    if (workspaceId) {
      window.localStorage.setItem(STORAGE_KEY, workspaceId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const value = useMemo(
    () => ({ selectedWorkspaceId, setSelectedWorkspaceId }),
    [selectedWorkspaceId, setSelectedWorkspaceId],
  );

  return (
    <WorkspaceSelectionContext.Provider value={value}>
      {children}
    </WorkspaceSelectionContext.Provider>
  );
}

export function useWorkspaceSelection(): WorkspaceSelectionContextValue {
  const context = useContext(WorkspaceSelectionContext);
  if (!context) {
    throw new Error(
      "useWorkspaceSelection must be used within a WorkspaceSelectionProvider",
    );
  }
  return context;
}
