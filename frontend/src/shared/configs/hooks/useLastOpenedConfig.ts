import { useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@shared/storage";

const buildStorageKey = (workspaceId: string) => `ade.ui.workspace.${workspaceId}.configs.last`;

type StoredSelection = { readonly configId?: string | null } | null;

export function useLastOpenedConfig(workspaceId: string) {
  const storage = useMemo(() => createScopedStorage(buildStorageKey(workspaceId)), [workspaceId]);
  const [configId, setConfigId] = useState<string | null>(() => storage.get<StoredSelection>()?.configId ?? null);

  useEffect(() => {
    setConfigId(storage.get<StoredSelection>()?.configId ?? null);
  }, [storage]);

  const remember = (id: string) => {
    storage.set({ configId: id });
    setConfigId(id);
  };

  const clear = () => {
    storage.clear();
    setConfigId(null);
  };

  return { lastConfigId: configId, remember, clear } as const;
}
