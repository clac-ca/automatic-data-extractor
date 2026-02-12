import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@/lib/storage";
import { uiStorageKeys } from "@/lib/uiStorageKeys";

import {
  DEFAULT_PREVIEW_DISPLAY_PREFERENCES,
  isPreviewDisplayPreferences,
  type PreviewDisplayPreferences,
} from "../model";

function cloneDefaultPreferences(): PreviewDisplayPreferences {
  return { ...DEFAULT_PREVIEW_DISPLAY_PREFERENCES };
}

export function usePreviewDisplayPreferences(workspaceId: string) {
  const storage = useMemo(
    () => createScopedStorage(uiStorageKeys.documentsDetailPreviewDisplay(workspaceId)),
    [workspaceId],
  );

  const [preferences, setPreferences] = useState<PreviewDisplayPreferences>(() => {
    const stored = storage.get<unknown>();
    return isPreviewDisplayPreferences(stored) ? stored : cloneDefaultPreferences();
  });

  useEffect(() => {
    const stored = storage.get<unknown>();
    setPreferences(isPreviewDisplayPreferences(stored) ? stored : cloneDefaultPreferences());
  }, [storage]);

  useEffect(() => {
    storage.set(preferences);
  }, [preferences, storage]);

  const setTrimEmptyRows = useCallback((enabled: boolean) => {
    setPreferences((current) => (current.trimEmptyRows === enabled ? current : { ...current, trimEmptyRows: enabled }));
  }, []);

  const setTrimEmptyColumns = useCallback((enabled: boolean) => {
    setPreferences((current) =>
      current.trimEmptyColumns === enabled ? current : { ...current, trimEmptyColumns: enabled },
    );
  }, []);

  const setCompactMode = useCallback((enabled: boolean) => {
    setPreferences((current) =>
      current.trimEmptyRows === enabled && current.trimEmptyColumns === enabled
        ? current
        : { ...current, trimEmptyRows: enabled, trimEmptyColumns: enabled },
    );
  }, []);

  const reset = useCallback(() => {
    setPreferences(cloneDefaultPreferences());
  }, []);

  return {
    preferences,
    isCompactMode: preferences.trimEmptyRows && preferences.trimEmptyColumns,
    setTrimEmptyRows,
    setTrimEmptyColumns,
    setCompactMode,
    reset,
  };
}
