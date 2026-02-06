import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { WorkbenchFileMetadata, WorkbenchFileNode, WorkbenchFileTab } from "../types";
import { findFileNode, findFirstFile } from "../utils/tree";

interface WorkbenchFilesPersistence {
  readonly get: <T>() => T | null;
  readonly set: <T>(value: T) => void;
  readonly clear: () => void;
}

interface PersistedWorkbenchTabEntry {
  readonly id: string;
  readonly pinned?: boolean;
}

interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | PersistedWorkbenchTabEntry)[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}

interface UseWorkbenchFilesOptions {
  readonly tree: WorkbenchFileNode | null;
  readonly initialActiveFileId?: string;
  readonly loadFile: (fileId: string) => Promise<{ content: string; etag?: string | null }>;
  readonly persistence?: WorkbenchFilesPersistence | null;
}

type WorkbenchTabZone = "pinned" | "regular";

interface WorkbenchFilesApi {
  readonly tree: WorkbenchFileNode | null;
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly activeTab: WorkbenchFileTab | null;
  readonly openFile: (fileId: string) => void;
  readonly selectTab: (fileId: string) => void;
  readonly closeTab: (fileId: string) => void;
  readonly closeOtherTabs: (fileId: string) => void;
  readonly closeTabsToRight: (fileId: string) => void;
  readonly closeAllTabs: () => void;
  readonly moveTab: (fileId: string, targetIndex: number) => void;
  readonly reloadTab: (fileId: string) => void;
  readonly pinTab: (fileId: string) => void;
  readonly unpinTab: (fileId: string) => void;
  readonly toggleTabPin: (fileId: string, pinned: boolean) => void;
  readonly selectRecentTab: (direction: "forward" | "backward") => void;
  readonly updateContent: (fileId: string, content: string) => void;
  readonly beginSavingTab: (fileId: string) => void;
  readonly completeSavingTab: (
    fileId: string,
    options?: { metadata?: WorkbenchFileMetadata; etag?: string | null; savedContent?: string },
  ) => void;
  readonly failSavingTab: (fileId: string, message: string) => void;
  readonly replaceTabContent: (
    fileId: string,
    payload: { content: string; metadata?: WorkbenchFileMetadata; etag?: string | null },
  ) => void;
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
  const [recentOrder, setRecentOrder] = useState<string[]>([]);
  const [hasHydratedPersistence, setHasHydratedPersistence] = useState(() => !persistence);
  const [hasOpenedInitialTab, setHasOpenedInitialTab] = useState(false);
  const pendingLoadsRef = useRef<Set<string>>(new Set());
  const tabsRef = useRef<WorkbenchFileTab[]>([]);
  const activeTabIdRef = useRef<string>("");
  const recentOrderRef = useRef<string[]>([]);

  const setActiveTab = useCallback((nextActiveId: string) => {
    setActiveTabId((prev) => (prev === nextActiveId ? prev : nextActiveId));
    setRecentOrder((current) => {
      const sanitized = current.filter((id) => tabsRef.current.some((tab) => tab.id === id));
      if (!nextActiveId) {
        return sanitized;
      }
      const withoutNext = sanitized.filter((id) => id !== nextActiveId);
      return [nextActiveId, ...withoutNext];
    });
  }, []);

  useEffect(() => {
    activeTabIdRef.current = activeTabId;
  }, [activeTabId]);

  useEffect(() => {
    recentOrderRef.current = recentOrder;
  }, [recentOrder]);

  useEffect(() => {
    if (!tree) {
      setTabs([]);
      setActiveTabId("");
      setRecentOrder([]);
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
    const prevActive = activeTabIdRef.current;
    if (!prevActive || !findFileNode(tree, prevActive)) {
      setActiveTab("");
    }
  }, [tree, setActiveTab]);

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
                  saving: false,
                  saveError: null,
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
          pinned: false,
          saving: false,
          saveError: null,
          lastSavedAt: null,
        };
        return [...current, nextTab];
      });
      if (options?.activate ?? true) {
        setActiveTab(fileId);
      }
    },
    [tree, setActiveTab],
  );

  useEffect(() => {
    if (hasHydratedPersistence || !persistence || !tree) {
      if (!persistence) {
        setHasHydratedPersistence(true);
      }
      return;
    }

    const snapshot = persistence.get<PersistedWorkbenchTabs>();
    const candidateEntries = snapshot?.openTabs ?? [];
    const normalizedEntries = candidateEntries
      .map((entry) => (typeof entry === "string" ? { id: entry, pinned: false } : entry))
      .filter((entry): entry is PersistedWorkbenchTabEntry => Boolean(entry && entry.id));

    if (normalizedEntries.length > 0) {
      const nextTabs: WorkbenchFileTab[] = [];

      for (const entry of normalizedEntries) {
        const node = findFileNode(tree, entry.id);
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
          pinned: Boolean(entry.pinned),
          saving: false,
          saveError: null,
          lastSavedAt: null,
        });
      }

      if (nextTabs.length > 0) {
        setTabs(nextTabs);
        const preferredActiveId =
          (snapshot?.activeTabId && nextTabs.some((tab) => tab.id === snapshot.activeTabId)
            ? snapshot.activeTabId
            : nextTabs[0]?.id) ?? "";
        setActiveTabId(preferredActiveId);
        const preferredMru =
          snapshot?.mru && snapshot.mru.length > 0 ? snapshot.mru : nextTabs.map((tab) => tab.id);
        const normalizedMru = preferredMru.filter((id) => nextTabs.some((tab) => tab.id === id));
        setRecentOrder(normalizedMru);
        setHasOpenedInitialTab(true);
      }
    }

    setHasHydratedPersistence(true);
  }, [hasHydratedPersistence, persistence, tree]);

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

  const selectTab = useCallback(
    (fileId: string) => {
      setActiveTab(fileId);
      setTabs((current) =>
        current.map((tab) =>
          tab.id === fileId && tab.status === "error" ? { ...tab, status: "loading", error: null } : tab,
        ),
      );
    },
    [setActiveTab],
  );

  const closeTab = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        const remaining = current.filter((tab) => tab.id !== fileId);
        const prevActive = activeTabIdRef.current;
        const nextActiveId =
          prevActive === fileId
            ? remaining[remaining.length - 1]?.id ?? ""
            : remaining.some((tab) => tab.id === prevActive)
              ? prevActive
              : remaining[remaining.length - 1]?.id ?? "";
        setActiveTab(nextActiveId);
        return remaining;
      });
    },
    [setActiveTab],
  );

  const closeOtherTabs = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        if (!current.some((tab) => tab.id === fileId) || current.length <= 1) {
          return current;
        }
        setActiveTab(fileId);
        return current.filter((tab) => tab.id === fileId);
      });
    },
    [setActiveTab],
  );

  const closeTabsToRight = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        const targetIndex = current.findIndex((tab) => tab.id === fileId);
        if (targetIndex === -1 || targetIndex === current.length - 1) {
          return current;
        }
        const next = current.slice(0, targetIndex + 1);
        const nextActiveId = next.some((tab) => tab.id === activeTabIdRef.current)
          ? activeTabIdRef.current
          : fileId;
        setActiveTab(nextActiveId);
        return next;
      });
    },
    [setActiveTab],
  );

  const closeAllTabs = useCallback(() => {
    setTabs([]);
    setActiveTabId("");
    setRecentOrder([]);
  }, []);

  const moveTab = useCallback((fileId: string, targetIndex: number) => {
    setTabs((current) => {
      if (current.length <= 1) {
        return current;
      }
      const fromIndex = current.findIndex((tab) => tab.id === fileId);
      if (fromIndex === -1) {
        return current;
      }
      const withoutMoving = current.filter((_, index) => index !== fromIndex);
      const boundedTarget = Math.max(0, Math.min(targetIndex, withoutMoving.length));
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      const moving = current[fromIndex];

      withoutMoving.forEach((tab) => {
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      });

      const zone: WorkbenchTabZone = boundedTarget <= pinned.length ? "pinned" : "regular";
      if (zone === "pinned") {
        const clampedIndex = Math.max(0, Math.min(boundedTarget, pinned.length));
        pinned.splice(clampedIndex, 0, { ...moving, pinned: true });
      } else {
        const relativeIndex = Math.max(0, Math.min(boundedTarget - pinned.length, regular.length));
        regular.splice(relativeIndex, 0, { ...moving, pinned: false });
      }

      return [...pinned, ...regular];
    });
  }, []);

  const reloadTab = useCallback(
    (fileId: string) => {
      if (pendingLoadsRef.current.has(fileId)) {
        return;
      }
      let found = false;
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          found = true;
          return { ...tab, status: "loading", error: null };
        }),
      );
      if (!found) {
        return;
      }
      pendingLoadsRef.current.add(fileId);
      loadIntoTab(fileId).finally(() => {
        pendingLoadsRef.current.delete(fileId);
      });
    },
    [loadIntoTab],
  );

  const pinTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      let target: WorkbenchFileTab | null = null;
      for (const tab of current) {
        if (tab.id === fileId) {
          target = tab;
          continue;
        }
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      }
      if (!target || target.pinned) {
        return current;
      }
      const updated = { ...target, pinned: true };
      return [...pinned, updated, ...regular];
    });
  }, []);

  const unpinTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      let target: WorkbenchFileTab | null = null;
      for (const tab of current) {
        if (tab.id === fileId) {
          target = tab;
          continue;
        }
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      }
      if (!target || !target.pinned) {
        return current;
      }
      const updated = { ...target, pinned: false };
      return [...pinned, updated, ...regular];
    });
  }, []);

  const toggleTabPin = useCallback(
    (fileId: string, pinned: boolean) => {
      if (pinned) {
        pinTab(fileId);
      } else {
        unpinTab(fileId);
      }
    },
    [pinTab, unpinTab],
  );

  const selectRecentTab = useCallback(
    (direction: "forward" | "backward") => {
      const ordered = recentOrderRef.current.filter((id) =>
        tabsRef.current.some((tab) => tab.id === id),
      );
      if (ordered.length <= 1) {
        return;
      }
      const activeId = activeTabIdRef.current || ordered[0];
      const currentIndex = ordered.indexOf(activeId);
      const safeIndex = currentIndex >= 0 ? currentIndex : 0;
      const delta = direction === "forward" ? 1 : -1;
      const nextIndex = (safeIndex + delta + ordered.length) % ordered.length;
      const nextId = ordered[nextIndex];
      if (nextId && nextId !== activeId) {
        setActiveTab(nextId);
      }
    },
    [setActiveTab],
  );

  const updateContent = useCallback((fileId: string, content: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              content,
              status: tab.status === "ready" ? tab.status : "ready",
              error: null,
              saveError: null,
            }
          : tab,
      ),
    );
  }, []);

  const beginSavingTab = useCallback((fileId: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              saving: true,
              saveError: null,
            }
          : tab,
      ),
    );
  }, []);

  const completeSavingTab = useCallback(
    (
      fileId: string,
      options?: { metadata?: WorkbenchFileMetadata; etag?: string | null; savedContent?: string },
    ) => {
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          const resolvedMetadata = options?.metadata ?? tab.metadata ?? null;
          const resolvedEtag = options?.etag ?? tab.etag ?? null;
          const savedContent = options?.savedContent ?? tab.content;
          return {
            ...tab,
            saving: false,
            saveError: null,
            initialContent: savedContent,
            etag: resolvedEtag,
            metadata: resolvedMetadata
              ? {
                  ...resolvedMetadata,
                  etag: resolvedMetadata.etag ?? resolvedEtag ?? null,
                }
              : resolvedMetadata,
            lastSavedAt: new Date().toISOString(),
          };
        }),
      );
    },
    [],
  );

  const failSavingTab = useCallback((fileId: string, message: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              saving: false,
              saveError: message,
            }
          : tab,
      ),
    );
  }, []);

  const replaceTabContent = useCallback(
    (fileId: string, payload: { content: string; metadata?: WorkbenchFileMetadata; etag?: string | null }) => {
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          return {
            ...tab,
            content: payload.content,
            initialContent: payload.content,
            status: "ready",
            error: null,
            saving: false,
            saveError: null,
            etag: payload.etag ?? tab.etag ?? null,
            metadata: payload.metadata ?? tab.metadata,
          };
        }),
      );
    },
    [],
  );

  const isDirty = useMemo(
    () => tabs.some((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );

  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  useEffect(() => {
    setRecentOrder((current) => {
      const filtered = current.filter((id) => tabs.some((tab) => tab.id === id));
      return filtered.length === current.length ? current : filtered;
    });
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
    const orderedRecentTabs = [activeTabId, ...recentOrder]
      .filter((id): id is string => Boolean(id))
      .filter((id, index, array) => array.indexOf(id) === index)
      .filter((id) => tabs.some((tab) => tab.id === id));
    persistence.set<PersistedWorkbenchTabs>({
      openTabs: tabs.map((tab) => ({ id: tab.id, pinned: Boolean(tab.pinned) })),
      activeTabId: activeTabId || null,
      mru: orderedRecentTabs,
    });
  }, [persistence, tabs, activeTabId, recentOrder, hasHydratedPersistence]);

  return {
    tree,
    tabs,
    activeTabId,
    activeTab,
    openFile,
    selectTab,
    closeTab,
    closeOtherTabs,
    closeTabsToRight,
    closeAllTabs,
    moveTab,
    reloadTab,
    pinTab,
    unpinTab,
    toggleTabPin,
    selectRecentTab,
    updateContent,
    beginSavingTab,
    completeSavingTab,
    failSavingTab,
    replaceTabContent,
    isDirty,
  };
}
