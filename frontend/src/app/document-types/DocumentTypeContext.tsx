import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface DocumentTypeContextValue {
  selections: Record<string, string | null>;
  setSelection: (workspaceId: string, documentType: string | null) => void;
  hydrateSelection: (workspaceId: string) => void;
  clearSelection: (workspaceId: string) => void;
}

const STORAGE_PREFIX = "ade.documentType.";

const DocumentTypeContext = createContext<DocumentTypeContextValue | undefined>(
  undefined,
);

function storageKey(workspaceId: string) {
  return `${STORAGE_PREFIX}${workspaceId}`;
}

function safeLocalStorage() {
  try {
    return window.localStorage;
  } catch (error) {
    return null;
  }
}

export function DocumentTypeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [selections, setSelections] = useState<Record<string, string | null>>({});

  const setSelection = useCallback((workspaceId: string, documentType: string | null) => {
    setSelections((current) => {
      if (current[workspaceId] === documentType) {
        return current;
      }
      return { ...current, [workspaceId]: documentType };
    });
    const store = safeLocalStorage();
    if (documentType) {
      store?.setItem(storageKey(workspaceId), documentType);
    } else {
      store?.removeItem(storageKey(workspaceId));
    }
  }, []);

  const hydrateSelection = useCallback((workspaceId: string) => {
    const store = safeLocalStorage();
    const stored = store?.getItem(storageKey(workspaceId)) ?? null;
    setSelections((current) => {
      if (current[workspaceId] === stored) {
        return current;
      }
      return { ...current, [workspaceId]: stored };
    });
  }, []);

  const clearSelection = useCallback((workspaceId: string) => {
    setSelections((current) => {
      if (current[workspaceId] === null || !(workspaceId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[workspaceId];
      return next;
    });
    safeLocalStorage()?.removeItem(storageKey(workspaceId));
  }, []);

  const value = useMemo(
    () => ({ selections, setSelection, hydrateSelection, clearSelection }),
    [clearSelection, hydrateSelection, selections, setSelection],
  );

  return (
    <DocumentTypeContext.Provider value={value}>
      {children}
    </DocumentTypeContext.Provider>
  );
}

export function useDocumentTypeContext() {
  const context = useContext(DocumentTypeContext);
  if (!context) {
    throw new Error(
      "useDocumentTypeContext must be used within a DocumentTypeProvider",
    );
  }
  return context;
}
