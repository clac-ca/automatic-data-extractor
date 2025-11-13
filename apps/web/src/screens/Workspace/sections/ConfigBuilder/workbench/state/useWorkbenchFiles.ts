import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { WorkbenchFileNode, WorkbenchFileTab } from "../types";
import { findFileNode, findFirstFile } from "../utils/tree";

interface WorkbenchFilesPersistence {
  readonly get: <T>() => T | null;
  readonly set: <T>(value: T) => void;
  readonly clear: () => void;
}

interface PersistedWorkbenchTabs {
  readonly openTabs: readonly string[];
  readonly activeTabId?: string | null;
}

interface UseWorkbenchFilesOptions {
  readonly tree: WorkbenchFileNode | null;
  readonly initialActiveFileId?: string;
  readonly loadFile: (fileId: string) => Promise<{ content: string; etag?: string | null }>;
  readonly persistence?: WorkbenchFilesPersistence | null;
}

interface WorkbenchFilesApi {
  readonly tree: WorkbenchFileNode | null;
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly activeTab: WorkbenchFileTab | null;
  readonly openFile: (fileId: string) => void;
  readonly selectTab: (fileId: string) => void;
  readonly closeTab: (fileId: string) => void;
  readonly updateContent: (fileId: string, content: string) => void;
  readonly isDirty: boolean;
}

export function useWorkbenchFiles({
  tree,
  initialActiveFileId,
  loadFile,
  persistence,
}: UseWorkbenchFilesOptions): WorkbenchFilesApi {
  const [tabs, setTabs] = useState<WorkbenchFileTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string>("");
  const [hasHydratedPersistence, setHasHydratedPersistence] = useState(() => !persistence);
  const [hasOpenedInitialTab, setHasOpenedInitialTab] = useState(false);
  const pendingLoadsRef = useRef<Set<string>>(new Set());
  const tabsRef = useRef<WorkbenchFileTab[]>([]);

  useEffect(() => {
    if (!tree) {
      setTabs([]);
      setActiveTabId("");
      return;
    }
    setTabs((current) =>
      current
        .filter((tab) => Boolean(findFileNode(tree, tab.id)))
        .map((tab) => {
          const node = findFileNode(tree, tab.id);
          if (!node || node.kind !== "file") {
            return tab;
          }
          return {
            ...tab,
            name: node.name,
            language: node.language,
            metadata: node.metadata,
          };
        }),
    );
    setActiveTabId((prev) => {
      if (prev && findFileNode(tree, prev)) {
        return prev;
      }
      return "";
    });
  }, [tree]);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0] ?? null,
    [activeTabId, tabs],
  );

  const loadIntoTab = useCallback(
    async (fileId: string) => {
      if (!tabsRef.current.some((tab) => tab.id === fileId)) {
        return;
      }
      let alreadyReady = false;
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          if (tab.status === "ready") {
            alreadyReady = true;
            return tab;
          }
          return { ...tab, status: "loading", error: null };
        }),
      );

      if (alreadyReady) {
        return;
      }

      try {
        const payload = await loadFile(fileId);
        setTabs((current) =>
          current.map((tab) =>
            tab.id === fileId
              ? {
                  ...tab,
                  initialContent: payload.content,
                  content: payload.content,
                  status: "ready",
                  error: null,
                  etag: payload.etag ?? null,
                }
              : tab,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to load file.";
        setTabs((current) =>
          current.map((tab) => (tab.id === fileId ? { ...tab, status: "error", error: message } : tab)),
        );
      }
    },
    [loadFile],
  );

  const ensureFileOpen = useCallback(
    (fileId: string, options?: { activate?: boolean }) => {
      if (!tree) {
        return;
      }
      const node = findFileNode(tree, fileId);
      if (!node || node.kind !== "file") {
        return;
      }
      setTabs((current) => {
        if (current.some((tab) => tab.id === fileId)) {
          return current;
        }
        const nextTab: WorkbenchFileTab = {
          id: node.id,
          name: node.name,
          language: node.language,
          initialContent: "",
          content: "",
          status: "loading",
          error: null,
          etag: null,
          metadata: node.metadata,
        };
        return [...current, nextTab];
      });
      if (options?.activate ?? true) {
        setActiveTabId(fileId);
      }
    },
    [tree],
  );

  useEffect(() => {
    if (hasHydratedPersistence) {
      return;
    }
    if (!persistence) {
      setHasHydratedPersistence(true);
      return;
    }
    if (!tree) {
      return;
    }

    const snapshot = persistence.get<PersistedWorkbenchTabs>();
    const candidateIds = snapshot?.openTabs ?? [];

    if (candidateIds.length > 0) {
      const nextTabs: WorkbenchFileTab[] = [];

      for (const id of candidateIds) {
        const node = findFileNode(tree, id);
        if (!node || node.kind !== "file") {
          continue;
        }
        nextTabs.push({
          id: node.id,
          name: node.name,
          language: node.language,
          initialContent: "",
          content: "",
          status: "loading",
          error: null,
          etag: null,
          metadata: node.metadata,
        });
      }

      if (nextTabs.length > 0) {
        setTabs(nextTabs);
        const preferredActiveId =
          (snapshot?.activeTabId && nextTabs.some((tab) => tab.id === snapshot.activeTabId)
            ? snapshot.activeTabId
            : nextTabs[0]?.id) ?? "";
        setActiveTabId(preferredActiveId);
        setHasOpenedInitialTab(true);
      }
    }

    setHasHydratedPersistence(true);
  }, [hasHydratedPersistence, persistence, tree, loadIntoTab]);

  useEffect(() => {
    if (!tree || !hasHydratedPersistence) {
      return;
    }
    if (tabs.length > 0) {
      if (!hasOpenedInitialTab) {
        setHasOpenedInitialTab(true);
      }
      return;
    }
    if (hasOpenedInitialTab) {
      return;
    }
    const preferred = (initialActiveFileId && findFileNode(tree, initialActiveFileId)) || findFirstFile(tree);
    if (!preferred) {
      setHasOpenedInitialTab(true);
      return;
    }
    ensureFileOpen(preferred.id);
    setHasOpenedInitialTab(true);
  }, [
    tree,
    initialActiveFileId,
    ensureFileOpen,
    hasHydratedPersistence,
    tabs.length,
    hasOpenedInitialTab,
  ]);

  const openFile = useCallback(
    (fileId: string) => {
      ensureFileOpen(fileId);
    },
    [ensureFileOpen],
  );

  const selectTab = useCallback((fileId: string) => {
    setActiveTabId(fileId);
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId && tab.status === "error" ? { ...tab, status: "loading", error: null } : tab,
      ),
    );
  }, []);

  const closeTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const remaining = current.filter((tab) => tab.id !== fileId);
      setActiveTabId((prev) => {
        if (prev === fileId) {
          return remaining[remaining.length - 1]?.id ?? "";
        }
        if (prev && remaining.some((tab) => tab.id === prev)) {
          return prev;
        }
        return remaining[remaining.length - 1]?.id ?? "";
      });
      return remaining;
    });
  }, []);

  const updateContent = useCallback((fileId: string, content: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              content,
              status: tab.status === "ready" ? tab.status : "ready",
              error: null,
            }
          : tab,
      ),
    );
  }, []);

  const isDirty = useMemo(
    () => tabs.some((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );

  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  useEffect(() => {
    const visibleTabIds = new Set(tabs.map((tab) => tab.id));
    for (const pendingId of pendingLoadsRef.current) {
      if (!visibleTabIds.has(pendingId)) {
        pendingLoadsRef.current.delete(pendingId);
      }
    }
    for (const tab of tabs) {
      if (tab.status !== "loading" || pendingLoadsRef.current.has(tab.id)) {
        continue;
      }
      pendingLoadsRef.current.add(tab.id);
      const pending = loadIntoTab(tab.id);
      pending.finally(() => {
        pendingLoadsRef.current.delete(tab.id);
      });
    }
  }, [tabs, loadIntoTab]);

  useEffect(() => {
    if (!persistence || !hasHydratedPersistence) {
      return;
    }
    persistence.set<PersistedWorkbenchTabs>({
      openTabs: tabs.map((tab) => tab.id),
      activeTabId: activeTabId || null,
    });
  }, [persistence, tabs, activeTabId, hasHydratedPersistence]);

  return {
    tree,
    tabs,
    activeTabId,
    activeTab,
    openFile,
    selectTab,
    closeTab,
    updateContent,
    isDirty,
  };
}
