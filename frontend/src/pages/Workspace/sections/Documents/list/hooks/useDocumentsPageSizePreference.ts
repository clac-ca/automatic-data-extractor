import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@/lib/storage";
import { uiStorageKeys } from "@/lib/uiStorageKeys";

import { normalizeDocumentsPageSize, type DocumentsPageSize } from "../../shared/constants";

function resolveStoredPageSize(value: unknown): DocumentsPageSize {
  return normalizeDocumentsPageSize(typeof value === "number" ? value : null);
}

export function readDocumentsPageSizePreference(value: unknown): DocumentsPageSize {
  return resolveStoredPageSize(value);
}

export function useDocumentsPageSizePreference(workspaceId: string) {
  const storage = useMemo(
    () => createScopedStorage(uiStorageKeys.documentsRowsPerPage(workspaceId)),
    [workspaceId],
  );

  const [pageSize, setPageSize] = useState<DocumentsPageSize>(() =>
    resolveStoredPageSize(storage.get<unknown>()),
  );

  useEffect(() => {
    setPageSize(resolveStoredPageSize(storage.get<unknown>()));
  }, [storage]);

  const setPageSizePreference = useCallback(
    (value: number) => {
      const normalized = normalizeDocumentsPageSize(value);
      setPageSize(normalized);
      storage.set(normalized);
    },
    [storage],
  );

  return {
    defaultPageSize: pageSize,
    setPageSizePreference,
  };
}
