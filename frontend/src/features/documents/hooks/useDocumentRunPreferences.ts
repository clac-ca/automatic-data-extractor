import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@shared/lib/storage";

export interface DocumentRunPreferences {
  readonly configurationId: string | null;
  readonly configurationVersion: number | null;
}

const DEFAULT_PREFERENCES: DocumentRunPreferences = {
  configurationId: null,
  configurationVersion: null,
};

function readPreferences(
  storage: ReturnType<typeof createScopedStorage>,
  documentId: string,
): DocumentRunPreferences {
  const all = storage.get<Record<string, DocumentRunPreferences>>();
  if (all && typeof all === "object" && documentId in all) {
    const entry = all[documentId];
    if (entry && typeof entry === "object") {
      return {
        configurationId: entry.configurationId ?? null,
        configurationVersion: entry.configurationVersion ?? null,
      };
    }
  }
  return DEFAULT_PREFERENCES;
}

export function useDocumentRunPreferences(workspaceId: string, documentId: string) {
  const storage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspaceId}.document_runs`),
    [workspaceId],
  );

  const [preferences, setPreferences] = useState<DocumentRunPreferences>(() =>
    readPreferences(storage, documentId),
  );

  useEffect(() => {
    setPreferences(readPreferences(storage, documentId));
  }, [storage, documentId]);

  const updatePreferences = useCallback(
    (next: DocumentRunPreferences) => {
      setPreferences(next);
      const all = storage.get<Record<string, DocumentRunPreferences>>() ?? {};
      storage.set({
        ...all,
        [documentId]: {
          configurationId: next.configurationId,
          configurationVersion: next.configurationVersion ?? null,
        },
      });
    },
    [storage, documentId],
  );

  return {
    preferences,
    setPreferences: updatePreferences,
  } as const;
}
