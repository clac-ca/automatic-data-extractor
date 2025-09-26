import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

const WORKSPACE_STORAGE_KEY = "ade-workspace-id";
const DOCUMENT_TYPE_STORAGE_KEY = "ade-document-type";

export interface WorkspaceSelection {
  readonly workspaceId: string | null;
  readonly documentType: string | null;
}

interface WorkspaceContextValue extends WorkspaceSelection {
  readonly setWorkspace: (workspaceId: string | null) => void;
  readonly setDocumentType: (documentType: string | null) => void;
  readonly clear: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

function readStoredValue(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(key);
}

function writeStoredValue(key: string, value: string | null): void {
  if (typeof window === "undefined") {
    return;
  }

  if (value) {
    window.localStorage.setItem(key, value);
  } else {
    window.localStorage.removeItem(key);
  }
}

interface WorkspaceProviderProps {
  readonly children: ReactNode;
}

export function WorkspaceProvider({ children }: WorkspaceProviderProps): JSX.Element {
  const [workspaceId, setWorkspaceId] = useState<string | null>(() =>
    readStoredValue(WORKSPACE_STORAGE_KEY)
  );
  const [documentType, setDocumentType] = useState<string | null>(() =>
    readStoredValue(DOCUMENT_TYPE_STORAGE_KEY)
  );

  useEffect(() => {
    writeStoredValue(WORKSPACE_STORAGE_KEY, workspaceId);
  }, [workspaceId]);

  useEffect(() => {
    writeStoredValue(DOCUMENT_TYPE_STORAGE_KEY, documentType);
  }, [documentType]);

  const handleSetWorkspace = useCallback((nextWorkspaceId: string | null) => {
    setWorkspaceId(nextWorkspaceId);
    setDocumentType(null);
  }, []);

  const handleSetDocumentType = useCallback((nextDocumentType: string | null) => {
    setDocumentType(nextDocumentType);
  }, []);

  const clear = useCallback(() => {
    setWorkspaceId(null);
    setDocumentType(null);
  }, []);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspaceId,
      documentType,
      setWorkspace: handleSetWorkspace,
      setDocumentType: handleSetDocumentType,
      clear
    }),
    [workspaceId, documentType, handleSetWorkspace, handleSetDocumentType, clear]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspaceContext(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);

  if (!context) {
    throw new Error("useWorkspaceContext must be used within a WorkspaceProvider");
  }

  return context;
}
