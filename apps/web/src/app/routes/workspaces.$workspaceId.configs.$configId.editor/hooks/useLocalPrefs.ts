import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@shared/storage";

export type ViewMode = "editor" | "split" | "zen";

export interface EditorLocalPrefs {
  readonly explorerWidth: number;
  readonly explorerCollapsed: boolean;
  readonly consoleHeight: number;
  readonly consoleOpen: boolean;
  readonly fontSize: number;
  readonly viewMode: ViewMode;
  readonly lastPath: string | null;
}

const DEFAULT_PREFS: EditorLocalPrefs = {
  explorerWidth: 260,
  explorerCollapsed: false,
  consoleHeight: 200,
  consoleOpen: false,
  fontSize: 13,
  viewMode: "editor",
  lastPath: null,
};

export function useLocalPrefs(storageKey: string) {
  const storage = useMemo(() => createScopedStorage(storageKey), [storageKey]);
  const [prefs, setPrefs] = useState<EditorLocalPrefs>(() => {
    const stored = storage.get<EditorLocalPrefs>();
    if (!stored) {
      return DEFAULT_PREFS;
    }
    return { ...DEFAULT_PREFS, ...stored };
  });

  useEffect(() => {
    storage.set(prefs);
  }, [prefs, storage]);

  const updatePrefs = useCallback((updater: Partial<EditorLocalPrefs> | ((prev: EditorLocalPrefs) => EditorLocalPrefs)) => {
    setPrefs((prev) =>
      typeof updater === "function"
        ? (updater as (prev: EditorLocalPrefs) => EditorLocalPrefs)(prev)
        : { ...prev, ...updater },
    );
  }, []);

  return { prefs, updatePrefs } as const;
}
