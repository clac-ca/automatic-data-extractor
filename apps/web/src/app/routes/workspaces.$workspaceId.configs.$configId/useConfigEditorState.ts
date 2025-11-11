import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { readConfigFileJson } from "@shared/configs/api";
import { useSaveConfigFileMutation } from "@shared/configs";
import type { FileReadJson, FileWriteResponse } from "@shared/configs";

interface UseConfigEditorStateOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly onSaved?: () => void;
}

export interface EditorTab {
  readonly path: string;
  readonly label: string;
  readonly status: "loading" | "ready" | "error";
  readonly encoding?: "utf-8" | "base64";
  readonly size?: number;
  readonly mtime?: string;
  readonly content: string;
  readonly originalContent: string;
  readonly etag?: string | null;
  readonly error?: string | null;
}

export function useConfigEditorState({ workspaceId, configId, onSaved }: UseConfigEditorStateOptions) {
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const tabsRef = useRef(tabs);
  const saveFile = useSaveConfigFileMutation(workspaceId, configId);

  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  const upsertTab = useCallback((next: Partial<EditorTab> & { path: string }) => {
    setTabs((prev) => {
      const existing = prev.find((tab) => tab.path === next.path);
      if (!existing) {
        const created: EditorTab = {
          path: next.path,
          label: extractLabel(next.path),
          status: next.status ?? "loading",
          content: next.content ?? "",
          originalContent: next.originalContent ?? "",
          encoding: next.encoding,
          size: next.size,
          mtime: next.mtime,
          etag: next.etag,
          error: next.error ?? null,
        };
        return [...prev, created];
      }
      return prev.map((tab) => (tab.path === next.path ? { ...tab, ...next } : tab));
    });
  }, []);

  const fetchFile = useCallback(
    async (path: string) => {
      try {
        const file = await readConfigFileJson(workspaceId, configId, path);
        upsertTab(mapFileToTab(file));
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to load file.";
        upsertTab({ path, status: "error", error: message });
      }
    },
    [configId, workspaceId, upsertTab],
  );

  const openTab = useCallback(
    (path: string) => {
      if (!path) {
        return;
      }
      setActivePath(path);
      setTabs((prev) => {
        if (prev.some((tab) => tab.path === path)) {
          return prev;
        }
        return [
          ...prev,
          {
            path,
            label: extractLabel(path),
            status: "loading",
            content: "",
            originalContent: "",
            error: null,
          },
        ];
      });
      void fetchFile(path);
    },
    [fetchFile],
  );

  const closeTab = useCallback((path: string) => {
    setTabs((prev) => prev.filter((tab) => tab.path !== path));
    setActivePath((previous) => {
      if (previous !== path) {
        return previous;
      }
      const remaining = tabsRef.current.filter((tab) => tab.path !== path);
      return remaining.at(-1)?.path ?? null;
    });
  }, []);

  const updateContent = useCallback((path: string, nextContent: string) => {
    setTabs((prev) =>
      prev.map((tab) =>
        tab.path === path
          ? {
              ...tab,
              content: nextContent,
              error: null,
            }
          : tab,
      ),
    );
  }, []);

  const activeTab = useMemo(() => tabs.find((tab) => tab.path === activePath) ?? null, [tabs, activePath]);

  const renameTabPath = useCallback((fromPath: string, toPath: string) => {
    setTabs((prev) =>
      prev.map((tab) =>
        tab.path === fromPath
          ? {
              ...tab,
              path: toPath,
              label: extractLabel(toPath),
            }
          : tab,
      ),
    );
    setActivePath((current) => {
      if (current === fromPath) {
        return toPath;
      }
      return current;
    });
  }, []);

  const saveActiveTab = useCallback(async () => {
    if (!activePath) {
      return;
    }
    const current = tabsRef.current.find((tab) => tab.path === activePath);
    if (!current || current.encoding !== "utf-8") {
      return;
    }
    try {
      const result = await saveFile.mutateAsync({
        path: current.path,
        content: current.content,
        etag: current.etag ?? undefined,
      });
      const nextEtag = resolveEtag(result, current);
      setTabs((prev) =>
        prev.map((tab) =>
          tab.path === current.path
            ? {
                ...tab,
                originalContent: tab.content,
                etag: nextEtag,
                size: result?.size ?? tab.size,
                mtime: result?.mtime ?? tab.mtime,
                error: null,
              }
            : tab,
        ),
      );
      onSaved?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to save file.";
      setTabs((prev) => prev.map((tab) => (tab.path === current.path ? { ...tab, error: message } : tab)));
    }
  }, [activePath, onSaved, saveFile]);

  return {
    tabs,
    activePath,
    activeTab,
    openTab,
    closeTab,
    setActivePath,
    updateContent,
    saveActiveTab,
    renameTabPath,
    isSaving: saveFile.isPending,
  } as const;
}

function extractLabel(path: string) {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function mapFileToTab(file: FileReadJson): EditorTab {
  return {
    path: file.path,
    label: extractLabel(file.path),
    status: "ready",
    encoding: file.encoding,
    content: file.encoding === "utf-8" ? file.content : "",
    originalContent: file.encoding === "utf-8" ? file.content : "",
    etag: file.etag ?? null,
    size: file.size,
    mtime: file.mtime,
    error: null,
  };
}

function resolveEtag(result: FileWriteResponse | undefined, previous: EditorTab) {
  if (!result) {
    return previous.etag ?? null;
  }
  if (typeof result.etag === "string" && result.etag.length > 0) {
    return result.etag;
  }
  return previous.etag ?? null;
}
