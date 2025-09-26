import { useEffect, useMemo } from "react";

import { useDocumentTypeContext } from "./DocumentTypeContext";

export function useDocumentTypeSelection(
  workspaceId: string | null,
  configurations: { document_type: string }[] | undefined,
) {
  const { selections, setSelection, hydrateSelection, clearSelection } =
    useDocumentTypeContext();

  const documentTypes = useMemo(() => {
    if (!configurations) {
      return [];
    }
    const unique = new Set<string>();
    for (const configuration of configurations) {
      if (configuration.document_type) {
        unique.add(configuration.document_type);
      }
    }
    return Array.from(unique);
  }, [configurations]);

  useEffect(() => {
    if (workspaceId) {
      hydrateSelection(workspaceId);
    }
  }, [workspaceId, hydrateSelection]);

  const key = workspaceId ?? "";
  const value = key ? selections[key] ?? null : null;

  useEffect(() => {
    if (!workspaceId) {
      return;
    }
    if (documentTypes.length === 0) {
      clearSelection(workspaceId);
      return;
    }
    if (!value || !documentTypes.includes(value)) {
      setSelection(workspaceId, documentTypes[0]);
    }
  }, [workspaceId, documentTypes, value, setSelection, clearSelection]);

  const setValue = (documentType: string | null) => {
    if (!workspaceId) {
      return;
    }
    if (!documentType) {
      clearSelection(workspaceId);
      return;
    }
    setSelection(workspaceId, documentType);
  };

  return {
    documentType: value,
    documentTypes,
    setDocumentType: setValue,
  } as const;
}
