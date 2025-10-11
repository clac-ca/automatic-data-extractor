import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { DocumentTypeDetailResponse } from "../../../shared/api/types";

interface DocumentTypeDetailContextValue {
  documentType: DocumentTypeDetailResponse;
  workspaceName: string;
  isConfigurationDrawerOpen: boolean;
  openConfigurationDrawer: () => void;
  closeConfigurationDrawer: () => void;
}

const DocumentTypeDetailContext = createContext<DocumentTypeDetailContextValue | undefined>(undefined);

interface DocumentTypeDetailProviderProps {
  documentType: DocumentTypeDetailResponse;
  workspaceName: string;
  children: ReactNode;
}

export function DocumentTypeDetailProvider({
  documentType,
  workspaceName,
  children,
}: DocumentTypeDetailProviderProps) {
  const [isConfigurationDrawerOpen, setIsConfigurationDrawerOpen] = useState(false);

  useEffect(() => {
    setIsConfigurationDrawerOpen(false);
  }, [documentType.id]);

  const openConfigurationDrawer = useCallback(() => {
    setIsConfigurationDrawerOpen(true);
  }, []);

  const closeConfigurationDrawer = useCallback(() => {
    setIsConfigurationDrawerOpen(false);
  }, []);

  const value = useMemo<DocumentTypeDetailContextValue>(
    () => ({
      documentType,
      workspaceName,
      isConfigurationDrawerOpen,
      openConfigurationDrawer,
      closeConfigurationDrawer,
    }),
    [
      documentType,
      workspaceName,
      isConfigurationDrawerOpen,
      openConfigurationDrawer,
      closeConfigurationDrawer,
    ],
  );

  return <DocumentTypeDetailContext.Provider value={value}>{children}</DocumentTypeDetailContext.Provider>;
}

export function useDocumentTypeDetail() {
  const context = useContext(DocumentTypeDetailContext);
  if (!context) {
    throw new Error("useDocumentTypeDetail must be used within a DocumentTypeDetailProvider");
  }

  return context;
}
