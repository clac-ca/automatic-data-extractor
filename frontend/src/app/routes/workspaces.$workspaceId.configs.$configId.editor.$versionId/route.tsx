import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import clsx from "clsx";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { Input } from "@ui/input";
import { CodeEditor, type CodeEditorHandle } from "@ui/code-editor";

import { ApiError } from "@shared/api";
import { useHotkeys } from "@shared/hooks/useHotkeys";
import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  activateVersion,
  archiveVersion,
  cloneVersion,
  findActiveVersion,
  parseManifest,
  permanentlyDeleteVersion,
  restoreVersion,
  testVersion,
  useConfigManifestQuery,
  useConfigScriptsQuery,
  useConfigScriptQuery,
  useConfigVersionsQuery,
  useConfigsQuery,
  useCreateScriptMutation,
  useUpdateScriptMutation,
  validateVersion,
  type ConfigRecord,
  type ConfigScriptSummary,
  type ConfigVersionRecord,
  type ConfigVersionTestResponse,
  type ConfigVersionValidateResponse,
  type ManifestColumn,
  type ParsedManifest,
} from "@shared/configs";

const TOOL_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "settings", label: "Settings" },
  { id: "quick-test", label: "Quick Test" },
  { id: "mapping-matrix", label: "Mapping Matrix" },
  { id: "issues", label: "Issues" },
  { id: "tables", label: "Tables" },
  { id: "versions", label: "Versions" },
  { id: "activate", label: "Activate" },
] as const;

const FILE_GROUPS: readonly { key: FileGroupKey; label: string }[] = [
  { key: "core", label: "Core" },
  { key: "columns", label: "Columns" },
  { key: "table", label: "Table" },
  { key: "other", label: "Other files" },
];

const CORE_FILES = ["startup.py", "run.py"] as const;

type ToolId = (typeof TOOL_ITEMS)[number]["id"];
type FileGroupKey = "core" | "columns" | "table" | "other";

type ActiveView =
  | { kind: "file"; path: string }
  | { kind: "tool"; id: ToolId };

interface FileEntry {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly group: FileGroupKey;
  readonly column?: ManifestColumn;
  readonly missing: boolean;
  readonly disabled: boolean;
  readonly language?: string | null;
}

interface FileGroup {
  readonly key: FileGroupKey;
  readonly label: string;
  readonly entries: readonly FileEntry[];
}

interface TestInputValues {
  readonly documentId?: string;
  readonly notes?: string;
}

interface ValidationState {
  readonly status: "idle" | "running" | "success" | "error" | "stale";
  readonly ready?: boolean;
  readonly filesHash?: string;
  readonly problems: readonly string[];
  readonly message?: string;
  readonly response?: ConfigVersionValidateResponse | null;
  readonly completedAt?: string;
}

interface TestState {
  readonly status: "idle" | "running" | "success" | "error" | "stale";
  readonly response?: ConfigVersionTestResponse;
  readonly message?: string;
  readonly completedAt?: string;
  readonly responseCompletedAt?: string;
  readonly lastDocumentId?: string;
  readonly lastNotes?: string;
}

interface ConsoleEntry {
  readonly id: string;
  readonly tab: ConsoleTab;
  readonly title: string;
  readonly detail?: string;
  readonly createdAt: string;
}

type ConsoleTab = "problems" | "logs" | "timing";

export const handle = { workspaceSectionId: "configurations" } as const;

export default function WorkspaceConfigEditorRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const params = useParams<{ configId: string; versionId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const configId = params.configId ?? "";
  const versionIdParam = params.versionId ?? "";

  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });
  const configs = configsQuery.data ?? [];
  const activeConfig = useMemo<ConfigRecord | null>(
    () => configs.find((config) => config.config_id === configId) ?? null,
    [configs, configId],
  );

  const includeArchived = searchParams.get("showArchived") === "1";
  const versionsQuery = useConfigVersionsQuery({
    workspaceId: workspace.id,
    configId,
    includeDeleted: includeArchived,
    enabled: Boolean(configId),
  });

  const versions = useMemo<ConfigVersionRecord[]>(() => versionsQuery.data ?? [], [versionsQuery.data]);
  const orderedVersions = useMemo(
    () =>
      [...versions].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      ),
    [versions],
  );
  const visibleVersions = useMemo(
    () => (includeArchived ? orderedVersions : orderedVersions.filter((version) => !version.deleted_at)),
    [includeArchived, orderedVersions],
  );

  const selectedVersion = useMemo(
    () => visibleVersions.find((version) => version.config_version_id === versionIdParam) ?? null,
    [versionIdParam, visibleVersions],
  );

  useEffect(() => {
    if (!configId || visibleVersions.length === 0) {
      return;
    }
    if (selectedVersion) {
      return;
    }
    const fallback = findActiveVersion(visibleVersions) ?? visibleVersions[0] ?? null;
    if (!fallback) {
      return;
    }
    navigate(
      { pathname: `../${fallback.config_version_id}`, search: searchParams.toString() },
      { replace: true, relative: "path" },
    );
  }, [configId, navigate, searchParams, selectedVersion, visibleVersions]);

  const selectedVersionId = selectedVersion?.config_version_id ?? versionIdParam;
  const isActiveVersion = selectedVersion?.status === "active";
  const isArchivedVersion = Boolean(selectedVersion?.deleted_at);

  const manifestQuery = useConfigManifestQuery({
    workspaceId: workspace.id,
    configId,
    versionId: selectedVersionId,
    enabled: Boolean(selectedVersionId),
  });
  const manifest = useMemo(() => parseManifest(manifestQuery.data?.manifest), [manifestQuery.data]);

  const scriptsQuery = useConfigScriptsQuery({
    workspaceId: workspace.id,
    configId,
    versionId: selectedVersionId,
    enabled: Boolean(selectedVersionId),
  });
  const scripts = scriptsQuery.data ?? [];

  const fileEntries = useMemo(() => buildFileEntries(manifest.columns, manifest.table, scripts), [manifest, scripts]);
  const fileGroups = useMemo(() => buildFileGroups(fileEntries), [fileEntries]);
  useEffect(() => {
    setRecentFiles((current) => current.filter((path) => fileEntries.some((entry) => entry.path === path)));
  }, [fileEntries]);
  const recentEntries = useMemo(
    () =>
      recentFiles
        .map((path) => fileEntries.find((entry) => entry.path === path) ?? null)
        .filter((entry): entry is FileEntry => entry !== null),
    [fileEntries, recentFiles],
  );
  const sanitizedPinnedTools = useMemo(
    () => pinnedTools.filter((toolId) => TOOL_ITEMS.some((tool) => tool.id === toolId)),
    [pinnedTools],
  );

  const requestedView = searchParams.get("view");
  const requestedFile = searchParams.get("file");
  const requestedTool = searchParams.get("tool") as ToolId | null;

  const defaultFilePath = fileEntries[0]?.path ?? "";

  const [activeView, setActiveView] = useState<ActiveView>(() => {
    if (requestedView === "tool" && requestedTool) {
      return { kind: "tool", id: requestedTool };
    }
    if (requestedFile && fileEntries.some((entry) => entry.path === requestedFile)) {
      return { kind: "file", path: requestedFile };
    }
    if (defaultFilePath) {
      return { kind: "file", path: defaultFilePath };
    }
    return { kind: "tool", id: "overview" };
  });

  useEffect(() => {
    if (activeView.kind === "file" && !fileEntries.some((entry) => entry.path === activeView.path)) {
      if (defaultFilePath) {
        setActiveView({ kind: "file", path: defaultFilePath });
      } else {
        setActiveView({ kind: "tool", id: "overview" });
      }
    }
  }, [activeView, defaultFilePath, fileEntries]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (activeView.kind === "file") {
      const currentView = next.get("view");
      const currentFile = next.get("file");
      const currentTool = next.get("tool");
      if (currentView === "file" && currentFile === activeView.path && !currentTool) {
        return;
      }
      next.set("view", "file");
      next.set("file", activeView.path);
      next.delete("tool");
    } else {
      const currentView = next.get("view");
      const currentTool = next.get("tool");
      const currentFile = next.get("file");
      if (currentView === "tool" && currentTool === activeView.id && !currentFile) {
        return;
      }
      next.set("view", "tool");
      next.set("tool", activeView.id);
      next.delete("file");
    }
    setSearchParams(next, { replace: true });
  }, [activeView, searchParams, setSearchParams]);

  const selectedFilePath = activeView.kind === "file" ? activeView.path : null;
  const selectedFileEntry = useMemo(
    () => (selectedFilePath ? fileEntries.find((entry) => entry.path === selectedFilePath) ?? null : null),
    [fileEntries, selectedFilePath],
  );

  const {
    data: scriptContent,
    refetch: refetchScript,
    isLoading: isScriptLoadingInitial,
    isFetching: isScriptFetching,
  } = useConfigScriptQuery(
    workspace.id,
    configId,
    selectedVersionId,
    selectedFilePath ?? "",
    Boolean(selectedFilePath && selectedVersionId),
  );

  const isScriptLoading = useMemo(
    () => isScriptLoadingInitial || (isScriptFetching && !scriptContent),
    [isScriptFetching, isScriptLoadingInitial, scriptContent],
  );

  const createScript = useCreateScriptMutation(workspace.id, configId, selectedVersionId);
  const updateScript = useUpdateScriptMutation(workspace.id, configId, selectedVersionId);

  const [editorValue, setEditorValue] = useState<string>("");
  const [currentSha, setCurrentSha] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [conflictDetected, setConflictDetected] = useState(false);
  const [lastSavedDescription, setLastSavedDescription] = useState<string>("");
  const [dirtyPaths, setDirtyPaths] = useState<Record<string, boolean>>({});
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<CodeEditorHandle | null>(null);

  const [consoleEntries, setConsoleEntries] = useState<ConsoleEntry[]>([]);
  const addConsoleEntry = useCallback(
    (entry: Omit<ConsoleEntry, "id">) => {
      setConsoleEntries((previous) => {
        const next = [
          ...previous,
          {
            ...entry,
            id: `${entry.tab}-${entry.createdAt}-${Math.random().toString(36).slice(2, 8)}`,
          },
        ];
        return next.slice(-200);
      });
    },
    [],
  );

  useEffect(() => {
    if (!selectedFilePath) {
      setEditorValue("");
      setCurrentSha(null);
      setDirtyPaths({});
      setSaveError(null);
      setConflictDetected(false);
      setLastSavedDescription("");
      return;
    }
    if (!scriptContent) {
      setEditorValue("");
      setCurrentSha(null);
      setDirtyPaths((previous) => ({ ...previous, [selectedFilePath]: false }));
      setSaveError(null);
      setConflictDetected(false);
      setLastSavedDescription("");
      return;
    }
    setEditorValue(scriptContent.code);
    setCurrentSha(scriptContent.sha256);
    setDirtyPaths((previous) => ({ ...previous, [selectedFilePath]: false }));
    setSaveError(null);
    setConflictDetected(false);
    setLastSavedDescription(formatSavedDescription(scriptContent.sha256));
  }, [scriptContent, selectedFilePath]);

  const [validationStates, setValidationStates] = useState<Record<string, ValidationState>>({});
  const [testStates, setTestStates] = useState<Record<string, TestState>>({});
  const [testInputs, setTestInputs] = useState<Record<string, TestInputValues>>({});
  const [recentFiles, setRecentFiles] = useState<string[]>([]);
  const [fileQuery, setFileQuery] = useState<string>("");
  const [pinnedTools, setPinnedTools] = useState<readonly ToolId[]>(["mapping-matrix", "quick-test"]);
  const [isHarnessOpen, setIsHarnessOpen] = useState(false);
  const [harnessTab, setHarnessTab] = useState<"synthetic" | "quick-test">("synthetic");
  const [harnessInputs, setHarnessInputs] = useState<Record<string, HarnessInputState>>({});

  useEffect(() => {
    setValidationStates({});
    setTestStates({});
    setTestInputs({});
  }, [configId]);

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    setValidationStates((previous) => {
      if (previous[selectedVersionId]) {
        return previous;
      }
      return { ...previous, [selectedVersionId]: createEmptyValidationState() };
    });
  }, [selectedVersionId]);

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    const stored = testInputs[selectedVersionId];
    setTestStates((previous) => {
      if (previous[selectedVersionId]) {
        return previous;
      }
      return { ...previous, [selectedVersionId]: createEmptyTestState(stored) };
    });
  }, [selectedVersionId, testInputs]);

  const validationState = selectedVersionId
    ? validationStates[selectedVersionId] ?? createEmptyValidationState()
    : createEmptyValidationState();
  const testState = selectedVersionId ? testStates[selectedVersionId] ?? createEmptyTestState() : createEmptyTestState();

  const markValidationStale = useCallback(() => {
    if (!selectedVersionId) {
      return;
    }
    setValidationStates((previous) => {
      const current = previous[selectedVersionId];
      if (!current || current.status === "idle") {
        return previous;
      }
      return {
        ...previous,
        [selectedVersionId]: { ...current, status: "stale" },
      };
    });
  }, [selectedVersionId]);

  const markTestStale = useCallback(() => {
    if (!selectedVersionId) {
      return;
    }
    setTestStates((previous) => {
      const current = previous[selectedVersionId];
      if (!current || current.status === "idle") {
        return previous;
      }
      return {
        ...previous,
        [selectedVersionId]: { ...current, status: "stale" },
      };
    });
  }, [selectedVersionId]);

  const isCurrentFileDirty = selectedFilePath ? Boolean(dirtyPaths[selectedFilePath]) : false;

  const handlePersist = useCallback(async () => {
    if (
      isActiveVersion ||
      isArchivedVersion ||
      isScriptLoading ||
      !selectedFilePath ||
      !selectedVersionId ||
      scriptContent == null
    ) {
      return;
    }
    if (!dirtyPaths[selectedFilePath]) {
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      const result = await updateScript.mutateAsync({
        path: selectedFilePath,
        code: editorValue,
        etag: currentSha,
      });
      setCurrentSha(result.sha256);
      setDirtyPaths((previous) => ({ ...previous, [selectedFilePath]: false }));
      setConflictDetected(false);
      setLastSavedDescription(formatSavedDescription(result.sha256));
      markValidationStale();
      markTestStale();
      addConsoleEntry({
        tab: "logs",
        title: `Saved ${selectedFilePath}`,
        createdAt: new Date().toISOString(),
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 412) {
        setConflictDetected(true);
        setSaveError("Newer changes detected. Reload to continue editing.");
      } else {
        setSaveError(error instanceof Error ? error.message : "Failed to save file.");
      }
      addConsoleEntry({
        tab: "problems",
        title: `Failed to save ${selectedFilePath}`,
        detail: error instanceof Error ? error.message : undefined,
        createdAt: new Date().toISOString(),
      });
    } finally {
      setIsSaving(false);
    }
  }, [
    addConsoleEntry,
    currentSha,
    dirtyPaths,
    editorValue,
    isActiveVersion,
    isArchivedVersion,
    isScriptLoading,
    scriptContent,
    selectedFilePath,
    selectedVersionId,
    markValidationStale,
    markTestStale,
    updateScript,
  ]);

  useEffect(() => {
    if (!isCurrentFileDirty || isSaving || isActiveVersion || isArchivedVersion || conflictDetected || isScriptLoading) {
      return;
    }
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
    }
    saveTimer.current = setTimeout(() => {
      void handlePersist();
    }, 800);
    return () => {
      if (saveTimer.current) {
        clearTimeout(saveTimer.current);
      }
    };
  }, [
    conflictDetected,
    isCurrentFileDirty,
    handlePersist,
    isActiveVersion,
    isArchivedVersion,
    isSaving,
    isScriptLoading,
  ]);

  const handleReloadLatest = useCallback(() => {
    setConflictDetected(false);
    void refetchScript();
  }, [refetchScript]);

  const selectFile = useCallback(
    async (entry: FileEntry) => {
      if (!entry.path) {
        return;
      }
      if (entry.missing && !isActiveVersion && !isArchivedVersion) {
        try {
          await createScript.mutateAsync({
            path: entry.path,
            template: resolveScriptTemplate(entry.path, entry.column ?? null),
            language: guessScriptLanguage(entry.path),
          });
          await scriptsQuery.refetch();
          await refetchScript();
          markValidationStale();
          markTestStale();
        } catch (error) {
          addConsoleEntry({
            tab: "problems",
            title: `Unable to scaffold ${entry.path}`,
            detail: error instanceof Error ? error.message : undefined,
            createdAt: new Date().toISOString(),
          });
          return;
        }
      }
      setActiveView({ kind: "file", path: entry.path });
      setRecentFiles((current) => {
        const filtered = current.filter((path) => path !== entry.path);
        return [entry.path, ...filtered].slice(0, 12);
      });
      setTimeout(() => editorRef.current?.focus(), 0);
    },
    [
      addConsoleEntry,
      createScript,
      editorRef,
      isActiveVersion,
      isArchivedVersion,
      markTestStale,
      markValidationStale,
      refetchScript,
      setRecentFiles,
      scriptsQuery,
    ],
  );

  const handleToggleToolPin = useCallback((toolId: ToolId) => {
    setPinnedTools((current) => {
      const exists = current.includes(toolId);
      if (exists) {
        return current.filter((id) => id !== toolId);
      }
      return [toolId, ...current.filter((id) => id !== toolId)];
    });
  }, []);

  const selectTool = useCallback((tool: ToolId) => {
    setActiveView({ kind: "tool", id: tool });
  }, []);

  const handleEditorChange = useCallback(
    (value: string) => {
      setEditorValue(value);
      if (selectedFilePath) {
        setDirtyPaths((previous) => {
          if (previous[selectedFilePath]) {
            return previous;
          }
          return { ...previous, [selectedFilePath]: true };
        });
      }
      markValidationStale();
      markTestStale();
    },
    [markTestStale, markValidationStale, selectedFilePath],
  );

  const handleValidate = useCallback(async () => {
    if (!selectedVersionId) return;
    setValidationStates((previous) => ({
      ...previous,
      [selectedVersionId]: { ...previous[selectedVersionId], status: "running", problems: [] } as ValidationState,
    }));
    addConsoleEntry({
      tab: "logs",
      title: "Validation started",
      createdAt: new Date().toISOString(),
    });
    try {
      const result = await validateVersion(workspace.id, configId, selectedVersionId);
      const completedAt = new Date().toISOString();
      setValidationStates((previous) => ({
        ...previous,
        [selectedVersionId]: {
          status: result.ready ? "success" : "success",
          ready: result.ready,
          problems: result.problems ?? [],
          filesHash: result.files_hash ?? manifest.filesHash,
          message: result.ready ? undefined : "Validation reported problems.",
          response: result,
          completedAt,
        },
      }));
      addConsoleEntry({
        tab: result.problems?.length ? "problems" : "logs",
        title: result.problems?.length ? "Validation reported issues" : "Validation passed",
        detail: result.problems?.length ? `${result.problems.length} problems detected.` : undefined,
        createdAt: completedAt,
      });
    } catch (error) {
      const completedAt = new Date().toISOString();
      setValidationStates((previous) => ({
        ...previous,
        [selectedVersionId]: {
          status: "error",
          problems: [],
          message: error instanceof Error ? error.message : "Validation failed.",
          response: null,
          completedAt,
        },
      }));
      addConsoleEntry({
        tab: "problems",
        title: "Validation failed",
        detail: error instanceof Error ? error.message : undefined,
        createdAt,
      });
    }
  }, [addConsoleEntry, configId, manifest.filesHash, selectedVersionId, workspace.id]);

  const handleTest = useCallback(
    async (documentId: string, notes?: string) => {
      if (!selectedVersionId || !documentId) return;
      const trimmedNotes = notes?.trim() ?? undefined;
      setTestInputs((previous) => ({
        ...previous,
        [selectedVersionId]: { documentId, notes: trimmedNotes },
      }));
      setTestStates((previous) => ({
        ...previous,
        [selectedVersionId]: {
          ...previous[selectedVersionId],
          status: "running",
          message: undefined,
        },
      }));
      addConsoleEntry({
        tab: "logs",
        title: `Quick Test queued for ${documentId}`,
        createdAt: new Date().toISOString(),
      });
      try {
        const result = await testVersion(workspace.id, configId, selectedVersionId, documentId, trimmedNotes);
        const completedAt = new Date().toISOString();
        setTestStates((previous) => ({
          ...previous,
          [selectedVersionId]: {
            status: "success",
            response: result,
            completedAt,
            responseCompletedAt: completedAt,
            lastDocumentId: documentId,
            lastNotes: trimmedNotes,
          },
        }));
        addConsoleEntry({
          tab: result.findings?.length ? "problems" : "logs",
          title: result.findings?.length ? "Quick Test reported findings" : "Quick Test succeeded",
          detail: result.findings?.length ? `${result.findings.length} findings` : undefined,
          createdAt: completedAt,
        });
      } catch (error) {
        const completedAt = new Date().toISOString();
        setTestStates((previous) => ({
          ...previous,
          [selectedVersionId]: {
            status: "error",
            message: error instanceof Error ? error.message : "Test failed.",
            completedAt,
            lastDocumentId: documentId,
            lastNotes: trimmedNotes,
          },
        }));
        addConsoleEntry({
          tab: "problems",
          title: "Quick Test failed",
          detail: error instanceof Error ? error.message : undefined,
          createdAt: completedAt,
        });
      }
    },
    [addConsoleEntry, configId, selectedVersionId, workspace.id],
  );

  const hotkeys = useMemo(
    () => [
      {
        combo: "meta+s",
        handler: () => {
          void handlePersist();
        },
        options: { allowInInputs: true },
      },
      {
        combo: "ctrl+s",
        handler: () => {
          void handlePersist();
        },
        options: { allowInInputs: true },
      },
    ],
    [handlePersist],
  );

  useHotkeys(hotkeys);

  const [saveAsDialogTarget, setSaveAsDialogTarget] = useState<ConfigVersionRecord | null>(null);
  const [versionsMessage, setVersionsMessage] = useState<string | null>(null);

  const handleArchive = useCallback(
    async (version: ConfigVersionRecord) => {
      try {
        await archiveVersion(workspace.id, configId, version.config_version_id);
        await versionsQuery.refetch();
        setVersionsMessage(`Archived ${version.semver}`);
      } catch (error) {
        setVersionsMessage(error instanceof Error ? error.message : "Archive failed.");
      }
    },
    [configId, versionsQuery, workspace.id],
  );

  const handleRestore = useCallback(
    async (version: ConfigVersionRecord) => {
      try {
        await restoreVersion(workspace.id, configId, version.config_version_id);
        await versionsQuery.refetch();
        setVersionsMessage(`Restored ${version.semver}`);
      } catch (error) {
        setVersionsMessage(error instanceof Error ? error.message : "Restore failed.");
      }
    },
    [configId, versionsQuery, workspace.id],
  );

  const handleActivate = useCallback(
    async (version: ConfigVersionRecord) => {
      try {
        await activateVersion(workspace.id, configId, version.config_version_id);
        await versionsQuery.refetch();
        setVersionsMessage(`Activated ${version.semver}`);
      } catch (error) {
        setVersionsMessage(error instanceof Error ? error.message : "Activate failed.");
      }
    },
    [configId, versionsQuery, workspace.id],
  );

  const handleDeleteVersion = useCallback(
    async (version: ConfigVersionRecord) => {
      try {
        await permanentlyDeleteVersion(workspace.id, configId, version.config_version_id);
        await versionsQuery.refetch();
        setVersionsMessage(`Deleted ${version.semver}`);
      } catch (error) {
        setVersionsMessage(error instanceof Error ? error.message : "Delete failed.");
      }
    },
    [configId, versionsQuery, workspace.id],
  );

  const handleSaveAsNew = useCallback(
    async (source: ConfigVersionRecord, input: SaveAsNewVersionInput) => {
      try {
        await cloneVersion(workspace.id, configId, source.config_version_id, {
          semver: input.semver,
          message: input.message,
        });
        await versionsQuery.refetch();
        setVersionsMessage(`Cloned ${source.semver} to ${input.semver}`);
        setSaveAsDialogTarget(null);
      } catch (error) {
        throw error instanceof Error ? error : new Error("Save as new version failed.");
      }
    },
    [configId, versionsQuery, workspace.id],
  );

  const editorLanguage = useMemo(() => {
    if (scriptContent?.language) {
      return scriptContent.language;
    }
    if (selectedFileEntry?.language) {
      return selectedFileEntry.language;
    }
    if (selectedFilePath) {
      return guessScriptLanguage(selectedFilePath) ?? "plaintext";
    }
    return "plaintext";
  }, [scriptContent?.language, selectedFileEntry?.language, selectedFilePath]);

  const activeTool = activeView.kind === "tool" ? activeView.id : null;
  const functionAnchors = useMemo(() => extractFunctionAnchors(editorValue), [editorValue]);
  const harnessInput = useMemo(() => {
    if (!selectedFilePath) {
      return createEmptyHarnessInput();
    }
    return harnessInputs[selectedFilePath] ?? createEmptyHarnessInput();
  }, [harnessInputs, selectedFilePath]);

  const handleSelectFunction = useCallback(
    (line: number) => {
      editorRef.current?.revealLine(line);
    },
    [],
  );

  const handleToggleHarness = useCallback(() => {
    if (!selectedFilePath) {
      return;
    }
    setIsHarnessOpen((open) => {
      if (open) {
        return false;
      }
      setHarnessTab("synthetic");
      setHarnessInputs((previous) => {
        if (previous[selectedFilePath]) {
          return previous;
        }
        return { ...previous, [selectedFilePath]: createEmptyHarnessInput() };
      });
      return true;
    });
  }, [selectedFilePath]);

  const handleCloseHarness = useCallback(() => {
    setIsHarnessOpen(false);
  }, []);

  const handleHarnessInputChange = useCallback(
    (input: HarnessInputState) => {
      if (!selectedFilePath) {
        return;
      }
      setHarnessInputs((previous) => ({ ...previous, [selectedFilePath]: input }));
    },
    [selectedFilePath],
  );

  const handleRunHarness = useCallback(
    (input: HarnessInputState) => {
      addConsoleEntry({
        tab: "logs",
        title: `Harness queued for ${selectedFilePath ?? "file"}`,
        detail: "Synthetic harness execution is not wired yet.",
        createdAt: new Date().toISOString(),
      });
      handleHarnessInputChange(input);
    },
    [addConsoleEntry, handleHarnessInputChange, selectedFilePath],
  );

  useEffect(() => {
    if (activeView.kind !== "file") {
      setIsHarnessOpen(false);
    }
  }, [activeView]);

  return (
    <div className="flex h-full min-h-[calc(100vh-4rem)] bg-slate-50 text-slate-900">
      <LeftRail
        workspaceName={workspace.name}
        config={activeConfig}
        versions={visibleVersions}
        selectedVersionId={selectedVersionId}
        includeArchived={includeArchived}
        onToggleArchived={() => {
          const next = new URLSearchParams(searchParams);
          next.set("showArchived", includeArchived ? "0" : "1");
          setSearchParams(next, { replace: true });
        }}
        onSelectVersion={(versionId) => {
          navigate({ pathname: `../${versionId}`, search: searchParams.toString() }, { relative: "path" });
        }}
        fileGroups={fileGroups}
        recentEntries={recentEntries}
        fileQuery={fileQuery}
        onFileQueryChange={setFileQuery}
        selectedFilePath={selectedFilePath}
        selectedToolId={activeTool}
        onSelectFile={selectFile}
        onSelectTool={selectTool}
        dirtyPaths={dirtyPaths}
        pinnedTools={sanitizedPinnedTools}
        onToggleToolPin={handleToggleToolPin}
        isVersionLoading={versionsQuery.isLoading}
      />

      <main className="flex-1 overflow-hidden">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-sm font-semibold text-slate-900">{activeConfig?.name ?? "Configuration"}</h1>
              <p className="text-xs text-slate-500">
                Version {selectedVersion?.semver ?? "unspecified"} • Workspace {workspace.name}
              </p>
            </div>
            {activeView.kind === "file" ? (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                {isCurrentFileDirty ? <span className="text-amber-600">Unsaved</span> : null}
                {isSaving ? <span>Saving…</span> : null}
                {lastSavedDescription ? <span>{lastSavedDescription}</span> : null}
              </div>
            ) : null}
          </div>
        </header>

        <section className="flex h-[calc(100%-3.5rem)] flex-col">
          <div className="flex flex-1 overflow-hidden">
            {activeView.kind === "file" && selectedFilePath ? (
              <FileCanvas
                key={selectedFilePath}
                filePath={selectedFilePath}
                fileLabel={selectedFileEntry?.label ?? selectedFilePath}
                columnLabel={selectedFileEntry?.column?.label ?? null}
                language={editorLanguage ?? "plaintext"}
                value={editorValue}
                onChange={handleEditorChange}
                isReadOnly={isActiveVersion || isArchivedVersion}
                isLoading={isScriptLoading}
                error={saveError}
                conflictDetected={conflictDetected}
                onResolveConflict={handleReloadLatest}
                onSave={() => void handlePersist()}
                functionAnchors={functionAnchors}
                onSelectFunction={handleSelectFunction}
                onToggleHarness={handleToggleHarness}
                isHarnessOpen={isHarnessOpen}
                isDirty={isCurrentFileDirty}
                editorRef={editorRef}
              />
            ) : (
              <ToolCanvas
                activeTool={activeTool}
                manifest={manifest}
                validationState={validationState}
                onValidate={handleValidate}
                testState={testState}
                onTest={handleTest}
                testInputs={selectedVersionId ? testInputs[selectedVersionId] ?? {} : {}}
                versions={visibleVersions}
                selectedVersion={selectedVersion ?? null}
                onArchive={handleArchive}
                onRestore={handleRestore}
                onActivate={handleActivate}
                onDelete={handleDeleteVersion}
                onSaveAsNew={(version) => setSaveAsDialogTarget(version)}
                versionsMessage={versionsMessage}
                onDismissVersionsMessage={() => setVersionsMessage(null)}
              />
            )}
          </div>

          {selectedFilePath ? (
            <RunHarnessDrawer
              open={isHarnessOpen}
              onClose={handleCloseHarness}
              tab={harnessTab}
              onTabChange={(nextTab) => setHarnessTab(nextTab)}
              input={harnessInput}
              onChange={handleHarnessInputChange}
              onRun={handleRunHarness}
              testState={testState}
              currentFileLabel={selectedFileEntry?.label ?? selectedFilePath}
            />
          ) : null}

          <ConsolePanel entries={consoleEntries} />
        </section>
      </main>

      {saveAsDialogTarget ? (
        <SaveAsNewVersionDialog
          source={saveAsDialogTarget}
          onCancel={() => setSaveAsDialogTarget(null)}
          onConfirm={(input) => handleSaveAsNew(saveAsDialogTarget, input)}
        />
      ) : null}
    </div>
  );
}

interface RunHarnessDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly tab: "synthetic" | "quick-test";
  readonly onTabChange: (tab: "synthetic" | "quick-test") => void;
  readonly input: HarnessInputState;
  readonly onChange: (input: HarnessInputState) => void;
  readonly onRun: (input: HarnessInputState) => void;
  readonly testState: TestState;
  readonly currentFileLabel: string;
}

function RunHarnessDrawer({ open, onClose, tab, onTabChange, input, onChange, onRun, testState, currentFileLabel }: RunHarnessDrawerProps) {
  if (!open) {
    return null;
  }

  const handleInputChange = (field: keyof HarnessInputState, value: string) => {
    onChange({ ...input, [field]: value });
  };

  const quickTestResponse = testState.response ?? null;

  return (
    <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600 shadow-inner">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-900">Run harness · {currentFileLabel}</p>
          <p className="text-[11px] text-slate-500">Exercise detectors without leaving the canvas.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={clsx(
              "rounded px-2 py-1 text-[11px] font-semibold",
              tab === "synthetic" ? "bg-slate-900 text-white" : "bg-white text-slate-600",
            )}
            onClick={() => onTabChange("synthetic")}
          >
            Synthetic sample
          </button>
          <button
            type="button"
            className={clsx(
              "rounded px-2 py-1 text-[11px] font-semibold",
              tab === "quick-test" ? "bg-slate-900 text-white" : "bg-white text-slate-600",
            )}
            onClick={() => onTabChange("quick-test")}
          >
            From Quick Test
          </button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>

      {tab === "synthetic" ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,18rem),1fr]">
          <div className="space-y-3">
            <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Header example
              <Input
                value={input.header}
                onChange={(event) => handleInputChange("header", event.target.value)}
                placeholder="member_id"
                className="mt-1"
              />
            </label>
            <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Value sample
              <textarea
                value={input.value}
                onChange={(event) => handleInputChange("value", event.target.value)}
                rows={3}
                className="mt-1 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
                placeholder="12345"
              />
            </label>
            <Button size="sm" onClick={() => onRun(input)}>
              Run harness
            </Button>
            <p className="text-[11px] text-slate-500">
              Harness output currently logs to the console while we wire the visual waterfall.
            </p>
          </div>
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Preview</p>
            <p className="mt-2 text-sm text-slate-600">
              Provide a header and value to mimic spreadsheet input for this detector.
            </p>
            <p className="mt-2 text-[11px] text-slate-400">
              We never persist cell contents—only detector decisions.
            </p>
          </div>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          {quickTestResponse ? (
            <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-sm font-semibold text-slate-900">Latest Quick Test</p>
              <p className="text-[11px] text-slate-500">
                Document {quickTestResponse.document_id ?? "–"} • {quickTestResponse.findings?.length ?? 0} findings
              </p>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Column header
                <Input
                  value={input.quickTestColumn ?? ""}
                  onChange={(event) => handleInputChange("quickTestColumn", event.target.value)}
                  placeholder="member_id"
                  className="mt-1"
                />
              </label>
              <Button size="sm" onClick={() => onRun({ ...input, quickTestColumn: input.quickTestColumn ?? "" })}>
                Replay with Quick Test context
              </Button>
            </div>
          ) : (
            <Alert tone="info">Run a Quick Test to capture live detector context.</Alert>
          )}
        </div>
      )}
    </div>
  );
}

interface LeftRailProps {
  readonly workspaceName: string;
  readonly config: ConfigRecord | null;
  readonly versions: readonly ConfigVersionRecord[];
  readonly selectedVersionId: string | null;
  readonly includeArchived: boolean;
  readonly onToggleArchived: () => void;
  readonly onSelectVersion: (versionId: string) => void;
  readonly fileGroups: readonly FileGroup[];
  readonly recentEntries: readonly FileEntry[];
  readonly fileQuery: string;
  readonly onFileQueryChange: (value: string) => void;
  readonly selectedFilePath: string | null;
  readonly selectedToolId: ToolId | null;
  readonly onSelectFile: (entry: FileEntry) => void;
  readonly onSelectTool: (tool: ToolId) => void;
  readonly dirtyPaths: Readonly<Record<string, boolean>>;
  readonly pinnedTools: readonly ToolId[];
  readonly onToggleToolPin: (tool: ToolId) => void;
  readonly isVersionLoading: boolean;
}

function LeftRail({
  workspaceName,
  config,
  versions,
  selectedVersionId,
  includeArchived,
  onToggleArchived,
  onSelectVersion,
  fileGroups,
  recentEntries,
  fileQuery,
  onFileQueryChange,
  selectedFilePath,
  selectedToolId,
  onSelectFile,
  onSelectTool,
  dirtyPaths,
  pinnedTools,
  onToggleToolPin,
  isVersionLoading,
}: LeftRailProps) {
  const normalizedQuery = fileQuery.trim().toLowerCase();
  const filteredGroups = useMemo(() => {
    if (!normalizedQuery) {
      return fileGroups;
    }
    return fileGroups
      .map((group) => ({
        ...group,
        entries: group.entries.filter((entry) => {
          const haystack = [entry.label, entry.path, entry.column?.label, entry.column?.key]
            .filter(Boolean)
            .map((value) => value!.toLowerCase())
            .join(" ");
          return haystack.includes(normalizedQuery);
        }),
      }))
      .filter((group) => group.entries.length > 0);
  }, [fileGroups, normalizedQuery]);
  const showFileEmptyState = normalizedQuery.length > 0 && filteredGroups.length === 0;
  const recentVisible = !normalizedQuery && recentEntries.length > 0;
  const pinnedToolDetails = useMemo(
    () =>
      pinnedTools
        .map((toolId) => TOOL_ITEMS.find((tool) => tool.id === toolId) ?? null)
        .filter((value): value is (typeof TOOL_ITEMS)[number] => value !== null),
    [pinnedTools],
  );
  const remainingTools = useMemo(
    () => TOOL_ITEMS.filter((tool) => !pinnedToolDetails.some((entry) => entry.id === tool.id)),
    [pinnedToolDetails],
  );

  return (
    <aside className="flex w-80 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Workspace</p>
        <p className="text-sm font-medium text-slate-900">{workspaceName}</p>
        <p className="text-xs text-slate-500">{config?.name ?? "Configuration"}</p>
      </div>

      <div className="flex-1 overflow-auto px-2 pb-6 pt-3">
        <nav className="space-y-6 text-sm">
          <section>
            <header className="flex items-center justify-between px-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Versions</p>
              <button
                type="button"
                className="text-[11px] text-slate-500 hover:text-slate-700"
                onClick={onToggleArchived}
              >
                {includeArchived ? "Hide archived" : "Show archived"}
              </button>
            </header>
            <div className="mt-2 space-y-1">
              {isVersionLoading ? (
                <p className="px-2 text-xs text-slate-500">Loading versions…</p>
              ) : versions.length === 0 ? (
                <p className="px-2 text-xs text-slate-500">No versions yet.</p>
              ) : (
                versions.map((version) => (
                  <button
                    key={version.config_version_id}
                    type="button"
                    className={clsx(
                      "w-full rounded-lg px-2 py-1.5 text-left text-xs transition",
                      selectedVersionId === version.config_version_id
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:bg-slate-100",
                    )}
                    onClick={() => onSelectVersion(version.config_version_id)}
                  >
                    <span className="block font-medium text-slate-900/90">
                      {version.semver ?? "unspecified"}
                    </span>
                    <span className="block text-[11px] text-slate-500">{version.status}</span>
                  </button>
                ))
              )}
            </div>
          </section>

          <section>
            <header className="px-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Package Files</p>
            </header>
            <div className="mt-2 space-y-3">
              <Input
                value={fileQuery}
                onChange={(event) => onFileQueryChange(event.target.value)}
                placeholder="Filter files, fields, detectors…"
                className="w-full text-xs"
              />

              {recentVisible ? (
                <div>
                  <p className="px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Recently opened</p>
                  <ul className="mt-1 space-y-1">
                    {recentEntries.map((entry) => {
                      const isSelected = selectedFilePath === entry.path;
                      const isDirty = Boolean(dirtyPaths[entry.path]);
                      const badges = computeFileBadges(entry);
                      return (
                        <li key={`recent-${entry.id}`}>
                          <button
                            type="button"
                            onClick={() => onSelectFile(entry)}
                            className={clsx(
                              "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition",
                              isSelected ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
                            )}
                          >
                            <span className="flex min-w-0 items-center gap-1">
                              {isDirty ? <span className="text-amber-500">●</span> : null}
                              <span className="truncate">{entry.label}</span>
                            </span>
                            <span className="flex items-center gap-1">
                              {badges.map((badge) => (
                                <FileBadgePill key={`${entry.path}-${badge.code}`} badge={badge} />
                              ))}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : null}

              {filteredGroups.map((group) => (
                <div key={group.key}>
                  <p className="px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    {group.label}
                  </p>
                  <ul className="mt-1 space-y-1">
                    {group.entries.map((entry) => {
                      const isSelected = selectedFilePath === entry.path;
                      const isDirty = Boolean(dirtyPaths[entry.path]);
                      const badges = computeFileBadges(entry);
                      return (
                        <li key={entry.id}>
                          <button
                            type="button"
                            onClick={() => onSelectFile(entry)}
                            className={clsx(
                              "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition",
                              isSelected
                                ? "bg-slate-900 text-white"
                                : entry.disabled
                                  ? "text-slate-400"
                                  : "text-slate-600 hover:bg-slate-100",
                            )}
                          >
                            <span className="flex min-w-0 items-center gap-1">
                              {isDirty ? <span className="text-amber-500">●</span> : null}
                              <span className="truncate">{entry.label}</span>
                            </span>
                            <span className="flex items-center gap-1">
                              {badges.map((badge) => (
                                <FileBadgePill key={`${entry.path}-${badge.code}`} badge={badge} />
                              ))}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
              {showFileEmptyState ? (
                <p className="px-2 text-xs text-slate-500">No files matched “{fileQuery}”.</p>
              ) : null}
              {!normalizedQuery && fileGroups.length === 0 ? (
                <p className="px-2 text-xs text-slate-500">No files detected for this version.</p>
              ) : null}
            </div>
          </section>

          <section>
            <header className="px-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Workspace Tools</p>
            </header>
            <div className="mt-2 space-y-2">
              {pinnedToolDetails.length > 0 ? (
                <div>
                  <p className="px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Pinned</p>
                  <ul className="mt-1 space-y-1">
                    {pinnedToolDetails.map((tool) => (
                      <li key={`pinned-${tool.id}`}>
                        <ToolButton
                          tool={tool}
                          isSelected={selectedToolId === tool.id}
                          onSelect={onSelectTool}
                          isPinned
                          onTogglePin={onToggleToolPin}
                        />
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div>
                {pinnedToolDetails.length > 0 ? (
                  <p className="px-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">All tools</p>
                ) : null}
                <ul className="mt-1 space-y-1">
                  {remainingTools.map((tool) => (
                    <li key={tool.id}>
                      <ToolButton
                        tool={tool}
                        isSelected={selectedToolId === tool.id}
                        onSelect={onSelectTool}
                        isPinned={pinnedTools.includes(tool.id)}
                        onTogglePin={onToggleToolPin}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        </nav>
      </div>
    </aside>
  );
}

interface FileCanvasProps {
  readonly filePath: string;
  readonly fileLabel: string;
  readonly columnLabel: string | null;
  readonly language: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly isReadOnly: boolean;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly conflictDetected: boolean;
  readonly onResolveConflict: () => void;
  readonly onSave: () => void;
  readonly functionAnchors: readonly FunctionAnchor[];
  readonly onSelectFunction: (line: number) => void;
  readonly onToggleHarness: () => void;
  readonly isHarnessOpen: boolean;
  readonly isDirty: boolean;
  readonly editorRef: React.RefObject<CodeEditorHandle | null>;
}

function FileCanvas({
  filePath,
  fileLabel,
  columnLabel,
  language,
  value,
  onChange,
  isReadOnly,
  isLoading,
  error,
  conflictDetected,
  onResolveConflict,
  onSave,
  functionAnchors,
  onSelectFunction,
  onToggleHarness,
  isHarnessOpen,
  isDirty,
  editorRef,
}: FileCanvasProps) {
  const [selectedFunction, setSelectedFunction] = useState<string>("");

  useEffect(() => {
    setSelectedFunction("");
  }, [filePath, functionAnchors]);

  const handleFunctionChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = event.target.value;
    setSelectedFunction(next);
    if (next) {
      onSelectFunction(Number(next));
    }
  };

  const saveDisabled = isReadOnly || !isDirty;

  return (
    <div className="flex-1 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-2 text-slate-500">
          <span className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">{language}</span>
          <span className="max-w-[18rem] truncate font-mono text-[11px]">{filePath}</span>
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{fileLabel}</span>
          {columnLabel ? (
            <span className="rounded bg-emerald-100 px-2 py-0.5 text-[11px] text-emerald-700" title="Field label">
              {columnLabel}
            </span>
          ) : null}
          {functionAnchors.length > 0 ? (
            <select
              value={selectedFunction}
              onChange={handleFunctionChange}
              className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-600"
            >
              <option value="">Jump to function…</option>
              {functionAnchors.map((anchor) => (
                <option key={`${anchor.name}-${anchor.line}`} value={anchor.line}>
                  {anchor.name}
                </option>
              ))}
            </select>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={onToggleHarness}>
            {isHarnessOpen ? "Hide harness" : "Run harness"}
          </Button>
          <Button size="sm" variant="secondary" onClick={onSave} disabled={saveDisabled}>
            Save
          </Button>
        </div>
      </div>

      <div className="relative h-full">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-white/60 text-sm text-slate-500">
            Loading editor…
          </div>
        ) : null}
        <CodeEditor
          ref={editorRef}
          language={language}
          value={value}
          onChange={onChange}
          readOnly={isReadOnly}
          className="h-full"
        />
      </div>

      <div className="border-t border-slate-200 bg-white px-4 py-3 text-xs">
        {isReadOnly ? (
          <Alert tone="info">This version is read-only. Clone it to make edits.</Alert>
        ) : null}
        {conflictDetected ? (
          <Alert tone="danger">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs">
                A newer version of this file exists. Reload to continue editing safely.
              </p>
              <Button size="sm" onClick={onResolveConflict}>
                Reload latest
              </Button>
            </div>
          </Alert>
        ) : null}
        {error ? <Alert tone="danger">{error}</Alert> : null}
      </div>
    </div>
  );
}

interface ToolCanvasProps {
  readonly activeTool: ToolId | null;
  readonly manifest: ParsedManifest;
  readonly validationState: ValidationState;
  readonly onValidate: () => void;
  readonly testState: TestState;
  readonly onTest: (documentId: string, notes?: string) => void;
  readonly testInputs: TestInputValues;
  readonly versions: readonly ConfigVersionRecord[];
  readonly selectedVersion: ConfigVersionRecord | null;
  readonly onArchive: (version: ConfigVersionRecord) => void;
  readonly onRestore: (version: ConfigVersionRecord) => void;
  readonly onActivate: (version: ConfigVersionRecord) => void;
  readonly onDelete: (version: ConfigVersionRecord) => void;
  readonly onSaveAsNew: (version: ConfigVersionRecord) => void;
  readonly versionsMessage: string | null;
  readonly onDismissVersionsMessage: () => void;
}

function ToolCanvas({
  activeTool,
  manifest,
  validationState,
  onValidate,
  testState,
  onTest,
  testInputs,
  versions,
  selectedVersion,
  onArchive,
  onRestore,
  onActivate,
  onDelete,
  onSaveAsNew,
  versionsMessage,
  onDismissVersionsMessage,
}: ToolCanvasProps) {
  const toolId = activeTool ?? "overview";
  return (
    <div className="flex-1 overflow-auto bg-white">
      {toolId === "overview" ? (
        <OverviewTool manifest={manifest} validationState={validationState} testState={testState} />
      ) : null}
      {toolId === "settings" ? <SettingsTool manifest={manifest} /> : null}
      {toolId === "quick-test" ? (
        <QuickTestTool state={testState} onTest={onTest} defaults={testInputs} />
      ) : null}
      {toolId === "mapping-matrix" ? <MappingMatrixTool state={testState} /> : null}
      {toolId === "issues" ? <IssuesTool validationState={validationState} onValidate={onValidate} /> : null}
      {toolId === "tables" ? <TablesTool manifest={manifest} /> : null}
      {toolId === "versions" ? (
        <VersionsTool
          versions={versions}
          selected={selectedVersion}
          onArchive={onArchive}
          onRestore={onRestore}
          onActivate={onActivate}
          onDelete={onDelete}
          onSaveAsNew={onSaveAsNew}
          message={versionsMessage}
          onDismissMessage={onDismissVersionsMessage}
        />
      ) : null}
      {toolId === "activate" ? (
        <ActivateTool validationState={validationState} testState={testState} selectedVersion={selectedVersion} />
      ) : null}
    </div>
  );
}

interface OverviewToolProps {
  readonly manifest: ParsedManifest;
  readonly validationState: ValidationState;
  readonly testState: TestState;
}

function OverviewTool({ manifest, validationState, testState }: OverviewToolProps) {
  return (
    <section className="space-y-6 p-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Overview</h2>
        <p className="mt-1 text-sm text-slate-500">
          Everything you need to understand the state of this configuration at a glance.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Manifest" subtitle={`${manifest.columns.length} columns`}>
          <dl className="space-y-1 text-sm text-slate-600">
            <div className="flex items-center justify-between">
              <dt>Name</dt>
              <dd className="font-medium text-slate-900">{manifest.name || "Not specified"}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>Files hash</dt>
              <dd>
                <code className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">
                  {manifest.filesHash || "–"}
                </code>
              </dd>
            </div>
          </dl>
        </Card>

        <Card title="Validation" subtitle={formatValidationSummary(validationState)}>
          <p className="text-sm text-slate-600">
            {validationState.status === "success"
              ? validationState.ready
                ? "Manifest and scripts are ready to activate."
                : "Validation completed with issues."
              : validationState.status === "running"
                ? "Validation in progress…"
                : "Run validation to verify manifest and scripts."}
          </p>
        </Card>

        <Card title="Quick Test" subtitle={formatTestSummary(testState)}>
          <p className="text-sm text-slate-600">
            {testState.status === "success"
              ? "Quick Test completed successfully."
              : testState.status === "running"
                ? "Quick Test running…"
                : "Run a sample document to see mapping confidence and issues."}
          </p>
        </Card>

        <Card title="Next Steps" subtitle="High confidence changes">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
            <li>Review validation findings under Issues.</li>
            <li>Run a fresh Quick Test after editing scripts.</li>
            <li>Activate when the latest version passes validation and tests.</li>
          </ul>
        </Card>
      </div>
    </section>
  );
}

interface SettingsToolProps {
  readonly manifest: ParsedManifest;
}

function SettingsTool({ manifest }: SettingsToolProps) {
  const [mode, setMode] = useState<"form" | "raw">("form");
  return (
    <section className="space-y-4 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Settings</h2>
          <p className="text-sm text-slate-500">Switch between guided and raw manifest views.</p>
        </div>
        <div className="flex gap-2 text-xs">
          <Button size="sm" variant={mode === "form" ? "primary" : "secondary"} onClick={() => setMode("form")}>
            Form view
          </Button>
          <Button size="sm" variant={mode === "raw" ? "primary" : "secondary"} onClick={() => setMode("raw")}>
            Raw
          </Button>
        </div>
      </header>

      {mode === "form" ? (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
          <FormRow label="Package name" value={manifest.name || "Not specified"} />
          <FormRow label="Columns" value={`${manifest.columns.length} configured`} />
          <FormRow
            label="Table transform"
            value={manifest.table?.transform?.path ? manifest.table.transform.path : "Not configured"}
          />
          <FormRow
            label="Table validators"
            value={manifest.table?.validators?.path ? manifest.table.validators.path : "Not configured"}
          />
        </div>
      ) : (
        <pre className="overflow-auto rounded-2xl border border-slate-200 bg-slate-900 p-4 text-xs text-slate-200">
{JSON.stringify(manifest.raw ?? {}, null, 2)}
        </pre>
      )}
    </section>
  );
}

interface QuickTestToolProps {
  readonly state: TestState;
  readonly onTest: (documentId: string, notes?: string) => void;
  readonly defaults: TestInputValues;
}

function QuickTestTool({ state, onTest, defaults }: QuickTestToolProps) {
  const [documentId, setDocumentId] = useState(defaults.documentId ?? "");
  const [notes, setNotes] = useState(defaults.notes ?? "");

  useEffect(() => {
    setDocumentId(defaults.documentId ?? "");
    setNotes(defaults.notes ?? "");
  }, [defaults.documentId, defaults.notes]);

  const isRunning = state.status === "running";
  const hasResponse = Boolean(state.response);

  return (
    <section className="space-y-5 p-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Quick Test</h2>
        <p className="text-sm text-slate-500">Drop a document ID to run an ephemeral pipeline pass.</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,320px),1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Document ID
            <Input
              value={documentId}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setDocumentId(event.target.value)}
              className="mt-1"
              placeholder="doc_123"
            />
          </label>
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Notes (optional)
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="mt-1 h-24 w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
              placeholder="Context for this run"
            />
          </label>
          <Button
            className="mt-4 w-full"
            size="sm"
            onClick={() => onTest(documentId.trim(), notes.trim() ? notes.trim() : undefined)}
            disabled={!documentId.trim() || isRunning}
          >
            {isRunning ? "Running…" : "Run Quick Test"}
          </Button>

          {state.status === "error" ? (
            <Alert tone="danger" className="mt-4">
              {state.message ?? "Quick Test failed."}
            </Alert>
          ) : null}
          {state.status === "stale" ? (
            <Alert tone="warning" className="mt-4">
              Test results are stale after recent edits. Run again.
            </Alert>
          ) : null}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
          {isRunning && !hasResponse ? <p>Waiting for results…</p> : null}
          {!isRunning && !hasResponse ? (
            <p className="text-slate-500">No test has been run yet. Submit a document to see results.</p>
          ) : null}
          {state.status === "success" && state.response ? (
            <div className="space-y-3">
              <p className="font-semibold text-slate-900">{state.response.summary ?? "Quick Test completed."}</p>
              <dl className="space-y-1 text-xs text-slate-500">
                <div className="flex items-center justify-between">
                  <dt>Document</dt>
                  <dd className="font-mono text-[11px] text-slate-600">
                    {state.response.document_id ?? "–"}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt>Files hash</dt>
                  <dd>
                    <code className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">
                      {state.response.files_hash ?? "–"}
                    </code>
                  </dd>
                </div>
              </dl>
              {state.response.findings?.length ? (
                <div>
                  <p className="font-semibold text-slate-900">Findings</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-slate-600">
                    {state.response.findings.map((finding) => (
                      <li key={finding}>{finding}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-slate-500">No findings reported.</p>
              )}
              <details className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                <summary className="cursor-pointer font-semibold text-slate-700">View payload</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-900 px-3 py-2 font-mono text-[11px] text-slate-100">
{JSON.stringify(state.response, null, 2)}
                </pre>
              </details>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

interface MappingMatrixToolProps {
  readonly state: TestState;
}

function MappingMatrixTool({ state }: MappingMatrixToolProps) {
  const mapping = state.response?.mapping_matrix ?? [];
  const hasData = Array.isArray(mapping) && mapping.length > 0;
  return (
    <section className="space-y-4 p-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Mapping Matrix</h2>
        <p className="text-sm text-slate-500">
          Confidence by column. Click any cell to open the explain overlay in the future.
        </p>
      </header>

      {!state.response ? (
        <Alert tone="info">Run a Quick Test to populate the mapping matrix.</Alert>
      ) : null}

      {hasData ? (
        <div className="overflow-auto rounded-2xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-100 text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Column</th>
                <th className="px-3 py-2 text-left">Target</th>
                <th className="px-3 py-2 text-left">Confidence</th>
                <th className="px-3 py-2 text-left">Gate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white text-slate-700">
              {mapping.map((entry: any, index: number) => (
                <tr key={index}>
                  <td className="px-3 py-2 font-mono text-[11px]">{entry.source ?? "–"}</td>
                  <td className="px-3 py-2">{entry.target ?? "–"}</td>
                  <td className="px-3 py-2">{formatConfidence(entry.score)}</td>
                  <td className="px-3 py-2">{entry.passed ? "Mapped" : "Unmapped"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : state.response ? (
        <p className="text-sm text-slate-500">No mapping entries were returned for this test run.</p>
      ) : null}
    </section>
  );
}

interface IssuesToolProps {
  readonly validationState: ValidationState;
  readonly onValidate: () => void;
}

function IssuesTool({ validationState, onValidate }: IssuesToolProps) {
  const problems = validationState.problems ?? [];
  const isRunning = validationState.status === "running";
  return (
    <section className="space-y-4 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Issues</h2>
          <p className="text-sm text-slate-500">Validation findings grouped by code and severity.</p>
        </div>
        <Button size="sm" onClick={onValidate} disabled={isRunning}>
          {isRunning ? "Validating…" : "Run validation"}
        </Button>
      </header>

      {validationState.status === "running" ? (
        <Alert tone="info">Validation in progress…</Alert>
      ) : null}
      {validationState.status === "error" ? (
        <Alert tone="danger">{validationState.message ?? "Validation failed."}</Alert>
      ) : null}
      {validationState.status === "stale" ? (
        <Alert tone="warning">Validation results are stale after recent edits. Run again to refresh.</Alert>
      ) : null}

      {problems.length === 0 ? (
        <p className="text-sm text-slate-500">
          {validationState.status === "success"
            ? "Validation passed without issues."
            : "Run validation to populate this list."}
        </p>
      ) : (
        <div className="space-y-3">
          {problems.map((problem) => (
            <article
              key={problem}
              className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700"
            >
              {problem}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

interface TablesToolProps {
  readonly manifest: ParsedManifest;
}

function TablesTool({ manifest }: TablesToolProps) {
  const tableTransform = manifest.table?.transform?.path ?? null;
  const tableValidators = manifest.table?.validators?.path ?? null;
  return (
    <section className="space-y-4 p-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Tables</h2>
        <p className="text-sm text-slate-500">Inspect table-level transforms and validators.</p>
      </header>

      <div className="space-y-3">
        <Card title="Table transform" subtitle={tableTransform ? "Configured" : "Not configured"}>
          <p className="text-sm text-slate-600">
            {tableTransform ? (
              <code className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">
                {tableTransform}
              </code>
            ) : (
              "No table transform script configured."
            )}
          </p>
        </Card>

        <Card title="Table validators" subtitle={tableValidators ? "Configured" : "Not configured"}>
          <p className="text-sm text-slate-600">
            {tableValidators ? (
              <code className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">
                {tableValidators}
              </code>
            ) : (
              "No table validators script configured."
            )}
          </p>
        </Card>
      </div>
    </section>
  );
}

interface VersionsToolProps {
  readonly versions: readonly ConfigVersionRecord[];
  readonly selected: ConfigVersionRecord | null;
  readonly onArchive: (version: ConfigVersionRecord) => void;
  readonly onRestore: (version: ConfigVersionRecord) => void;
  readonly onActivate: (version: ConfigVersionRecord) => void;
  readonly onDelete: (version: ConfigVersionRecord) => void;
  readonly onSaveAsNew: (version: ConfigVersionRecord) => void;
  readonly message: string | null;
  readonly onDismissMessage: () => void;
}

function VersionsTool({
  versions,
  selected,
  onArchive,
  onRestore,
  onActivate,
  onDelete,
  onSaveAsNew,
  message,
  onDismissMessage,
}: VersionsToolProps) {
  return (
    <section className="space-y-5 p-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Versions</h2>
        <p className="text-sm text-slate-500">
          Clone, archive, restore, and activate configuration versions.
        </p>
      </header>

      {message ? (
        <Alert tone="info">
          <div className="flex items-center justify-between gap-3">
            <span>{message}</span>
            <Button size="sm" variant="ghost" onClick={onDismissMessage}>
              Dismiss
            </Button>
          </div>
        </Alert>
      ) : null}

      <div className="space-y-3">
        {versions.map((version) => {
          const isSelected = selected?.config_version_id === version.config_version_id;
          const isArchived = Boolean(version.deleted_at);
          const isActive = version.status === "active";
          return (
            <article
              key={version.config_version_id}
              className={clsx(
                "space-y-3 rounded-2xl border p-4 text-sm transition",
                isSelected ? "border-slate-900 shadow-lg" : "border-slate-200 bg-white",
              )}
            >
              <header className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{version.semver ?? "unspecified"}</p>
                  <p className="text-xs text-slate-500">Created {formatRelativeTime(version.created_at)}</p>
                </div>
                <span
                  className={clsx(
                    "rounded-full px-3 py-1 text-xs font-semibold",
                    isActive
                      ? "bg-emerald-100 text-emerald-700"
                      : isArchived
                        ? "bg-rose-100 text-rose-700"
                        : "bg-slate-100 text-slate-600",
                  )}
                >
                  {isActive ? "Active" : isArchived ? "Archived" : "Draft"}
                </span>
              </header>

              {version.message ? (
                <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{version.message}</p>
              ) : null}

              <div className="flex flex-wrap gap-2 text-xs">
                {!isArchived ? (
                  <Button size="sm" variant="secondary" onClick={() => onArchive(version)} disabled={isActive}>
                    Archive
                  </Button>
                ) : (
                  <Button size="sm" variant="secondary" onClick={() => onRestore(version)}>
                    Restore
                  </Button>
                )}
                <Button size="sm" variant="secondary" onClick={() => onSaveAsNew(version)}>
                  Save as new version
                </Button>
                <Button size="sm" variant="primary" onClick={() => onActivate(version)}>
                  Activate
                </Button>
                <Button size="sm" variant="danger" onClick={() => onDelete(version)}>
                  Delete
                </Button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

interface ActivateToolProps {
  readonly validationState: ValidationState;
  readonly testState: TestState;
  readonly selectedVersion: ConfigVersionRecord | null;
}

function ActivateTool({ validationState, testState, selectedVersion }: ActivateToolProps) {
  const readyForActivation =
    validationState.status === "success" && validationState.ready && testState.status === "success";
  return (
    <section className="space-y-4 p-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Activate</h2>
        <p className="text-sm text-slate-500">Preflight checklist before promoting this version.</p>
      </header>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
        <ChecklistItem
          checked={validationState.status === "success"}
          title="Validation run"
          description={formatValidationSummary(validationState)}
        />
        <ChecklistItem
          checked={testState.status === "success"}
          title="Quick Test"
          description={formatTestSummary(testState)}
        />
        <ChecklistItem
          checked={Boolean(selectedVersion?.message)}
          title="Release note"
          description={
            selectedVersion?.message
              ? "Release note provided."
              : "Consider documenting what changed in this version."
          }
        />
      </div>

      <Alert tone={readyForActivation ? "success" : "warning"}>
        {readyForActivation
          ? "Everything looks ready. Activate this version from the Versions tool."
          : "Resolve outstanding items before activating this version."}
      </Alert>
    </section>
  );
}

interface ConsolePanelProps {
  readonly entries: readonly ConsoleEntry[];
}

function ConsolePanel({ entries }: ConsolePanelProps) {
  const [activeTab, setActiveTab] = useState<ConsoleTab>("problems");
  const visible = entries.filter((entry) => entry.tab === activeTab);

  return (
    <footer className="border-t border-slate-200 bg-slate-900/95 text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 px-4">
        <nav className="flex gap-4 text-xs">
          <ConsoleTabButton
            label="Problems"
            count={entries.filter((entry) => entry.tab === "problems").length}
            active={activeTab === "problems"}
            onClick={() => setActiveTab("problems")}
          />
          <ConsoleTabButton
            label="Logs"
            count={entries.filter((entry) => entry.tab === "logs").length}
            active={activeTab === "logs"}
            onClick={() => setActiveTab("logs")}
          />
          <ConsoleTabButton
            label="Timing"
            count={entries.filter((entry) => entry.tab === "timing").length}
            active={activeTab === "timing"}
            onClick={() => setActiveTab("timing")}
          />
        </nav>
        <span className="text-[11px] text-slate-400">Shared console</span>
      </div>

      <div className="max-h-40 overflow-auto px-4 py-3 text-xs">
        {visible.length === 0 ? (
          <p className="text-slate-500">Nothing to show yet.</p>
        ) : (
          <ul className="space-y-2">
            {visible.map((entry) => (
              <li key={entry.id} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-100">{entry.title}</span>
                  <span className="text-[11px] text-slate-500">{formatRelativeTime(entry.createdAt)}</span>
                </div>
                {entry.detail ? <p className="text-slate-300">{entry.detail}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </footer>
  );
}

interface ConsoleTabButtonProps {
  readonly label: string;
  readonly count: number;
  readonly active: boolean;
  readonly onClick: () => void;
}

function ConsoleTabButton({ label, count, active, onClick }: ConsoleTabButtonProps) {
  return (
    <button
      type="button"
      className={clsx(
        "flex items-center gap-2 border-b-2 px-2 py-3 font-medium transition",
        active ? "border-white text-white" : "border-transparent text-slate-400 hover:text-white",
      )}
      onClick={onClick}
    >
      {label}
      <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px]">{count}</span>
    </button>
  );
}

interface CardProps {
  readonly title: string;
  readonly subtitle?: string;
  readonly children: ReactNode;
}

function Card({ title, subtitle, children }: CardProps) {
  return (
    <article className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
      <header>
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        {subtitle ? <p className="text-xs text-slate-500">{subtitle}</p> : null}
      </header>
      <div>{children}</div>
    </article>
  );
}

interface FormRowProps {
  readonly label: string;
  readonly value: string;
}

function FormRow({ label, value }: FormRowProps) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="text-sm text-slate-700">{value}</p>
    </div>
  );
}

interface ChecklistItemProps {
  readonly checked: boolean;
  readonly title: string;
  readonly description: string;
}

function ChecklistItem({ checked, title, description }: ChecklistItemProps) {
  return (
    <div className="flex items-start gap-3">
      <span
        className={clsx(
          "mt-1 flex h-5 w-5 items-center justify-center rounded-full border-2",
          checked ? "border-emerald-400 bg-emerald-500 text-white" : "border-slate-300 text-slate-400",
        )}
      >
        {checked ? "✓" : "○"}
      </span>
      <div>
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
    </div>
  );
}

interface FileBadge {
  readonly code: string;
  readonly tone: "neutral" | "warning";
  readonly label: string;
}

interface FileBadgePillProps {
  readonly badge: FileBadge;
}

function FileBadgePill({ badge }: FileBadgePillProps) {
  return (
    <span
      className={clsx(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        badge.tone === "warning" ? "bg-amber-100 text-amber-700" : "bg-slate-200 text-slate-700",
      )}
      title={badge.label}
    >
      {badge.code}
    </span>
  );
}

function computeFileBadges(entry: FileEntry): FileBadge[] {
  const badges: FileBadge[] = [];
  if (entry.group === "columns") {
    badges.push({ code: "M", tone: "neutral", label: "Column detector" });
  }
  if (/transform/i.test(entry.path)) {
    badges.push({ code: "T", tone: "neutral", label: "Transform" });
  }
  if (/validator/i.test(entry.path)) {
    badges.push({ code: "V", tone: "neutral", label: "Validator" });
  }
  if (entry.missing) {
    badges.push({ code: "!", tone: "warning", label: "Missing script" });
  }
  if (entry.disabled) {
    badges.push({ code: "Ø", tone: "warning", label: "Column disabled" });
  }
  return badges;
}

interface ToolButtonProps {
  readonly tool: (typeof TOOL_ITEMS)[number];
  readonly isSelected: boolean;
  readonly onSelect: (tool: ToolId) => void;
  readonly isPinned: boolean;
  readonly onTogglePin: (tool: ToolId) => void;
}

function ToolButton({ tool, isSelected, onSelect, isPinned, onTogglePin }: ToolButtonProps) {
  return (
    <div
      className={clsx(
        "flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition",
        isSelected ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
      )}
    >
      <button
        type="button"
        onClick={() => onSelect(tool.id)}
        className={clsx("flex-1 text-left", isSelected ? "text-white" : "text-current")}
      >
        {tool.label}
      </button>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onTogglePin(tool.id);
        }}
        className={clsx(
          "rounded px-1 text-[11px] font-semibold",
          isPinned ? "text-amber-400" : "text-slate-400 hover:text-slate-600",
        )}
        aria-label={isPinned ? `Unpin ${tool.label}` : `Pin ${tool.label}`}
      >
        {isPinned ? "★" : "☆"}
      </button>
    </div>
  );
}

interface SaveAsNewVersionInput {
  readonly semver: string;
  readonly message?: string;
}

interface SaveAsNewVersionDialogProps {
  readonly source: ConfigVersionRecord;
  readonly onCancel: () => void;
  readonly onConfirm: (input: SaveAsNewVersionInput) => Promise<void>;
}

function SaveAsNewVersionDialog({ source, onCancel, onConfirm }: SaveAsNewVersionDialogProps) {
  const [semver, setSemver] = useState(source.semver ?? "");
  const [message, setMessage] = useState(source.message ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm">
      <form
        className="w-[min(32rem,92vw)] space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
        onSubmit={async (event) => {
          event.preventDefault();
          const trimmedSemver = semver.trim();
          if (!trimmedSemver) {
            setError("Semantic version is required.");
            return;
          }
          setIsSubmitting(true);
          setError(null);
          try {
            await onConfirm({
              semver: trimmedSemver,
              message: message.trim() ? message.trim() : undefined,
            });
          } catch (error) {
            setError(error instanceof Error ? error.message : "Failed to save as new version.");
            if (mountedRef.current) {
              setIsSubmitting(false);
            }
            return;
          }
          if (mountedRef.current) {
            setIsSubmitting(false);
          }
        }}
      >
        <header className="space-y-1">
          <p className="text-sm font-semibold text-slate-900">Save as new version</p>
          <p className="text-xs text-slate-500">
            Clone{" "}
            <span className="font-semibold text-slate-700">{source.semver ?? "unspecified"}</span> into a new inactive
            version to safely explore changes.
          </p>
        </header>

        <div className="space-y-3 text-sm">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Semantic version
            <Input
              value={semver}
              onChange={(event) => setSemver(event.target.value)}
              placeholder="1.2.0"
              autoFocus
            />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Release note
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              className="mt-1 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
              rows={4}
              placeholder="Highlight what changed in this version"
            />
          </label>
        </div>

        {error ? <Alert tone="danger">{error}</Alert> : null}

        <footer className="flex justify-end gap-2 text-sm">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save as new version"}
          </Button>
        </footer>
      </form>
    </div>
  );
}

function buildFileEntries(
  columns: readonly ManifestColumn[],
  table: ParsedManifest["table"],
  scripts: readonly ConfigScriptSummary[],
): FileEntry[] {
  const scriptMap = new Map(scripts.map((script) => [script.path, script]));
  const entries: FileEntry[] = [];

  for (const file of CORE_FILES) {
    const script = scriptMap.get(file);
    entries.push({
      id: file,
      label: file,
      path: file,
      group: "core",
      missing: !script,
      disabled: false,
      language: script?.language ?? guessScriptLanguage(file) ?? null,
    });
  }

  const sortedColumns = [...columns].sort((a, b) => a.ordinal - b.ordinal);
  for (const column of sortedColumns) {
    const script = scriptMap.get(column.path);
    entries.push({
      id: column.key,
      label: column.label,
      path: column.path,
      group: "columns",
      column,
      missing: !script,
      disabled: column.enabled === false,
      language: script?.language ?? guessScriptLanguage(column.path) ?? null,
    });
  }

  if (table?.transform) {
    const script = scriptMap.get(table.transform.path);
    entries.push({
      id: "table-transform",
      label: "Table transform",
      path: table.transform.path,
      group: "table",
      missing: !script,
      disabled: false,
      language: script?.language ?? guessScriptLanguage(table.transform.path) ?? null,
    });
  }

  if (table?.validators) {
    const script = scriptMap.get(table.validators.path);
    entries.push({
      id: "table-validators",
      label: "Table validators",
      path: table.validators.path,
      group: "table",
      missing: !script,
      disabled: false,
      language: script?.language ?? guessScriptLanguage(table.validators.path) ?? null,
    });
  }

  const knownPaths = new Set(entries.map((entry) => entry.path));
  const otherScripts = scripts
    .filter((script) => !knownPaths.has(script.path))
    .map<FileEntry>((script) => ({
      id: script.config_script_id,
      label: script.path,
      path: script.path,
      group: "other",
      missing: false,
      disabled: false,
      language: script.language ?? guessScriptLanguage(script.path) ?? null,
    }));

  return [...entries, ...otherScripts];
}

function buildFileGroups(entries: readonly FileEntry[]): FileGroup[] {
  return FILE_GROUPS.map((group) => ({
    key: group.key,
    label: group.label,
    entries: entries.filter((entry) => entry.group === group.key),
  })).filter((group) => group.entries.length > 0);
}

function guessScriptLanguage(path: string): string | undefined {
  const lower = path.toLowerCase();
  if (lower.endsWith(".py")) {
    return "python";
  }
  if (lower.endsWith(".json")) {
    return "json";
  }
  if (lower.endsWith(".yaml") || lower.endsWith(".yml")) {
    return "yaml";
  }
  if (lower.endsWith(".sql")) {
    return "sql";
  }
  if (lower.endsWith(".jinja") || lower.endsWith(".j2")) {
    return "jinja";
  }
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) {
    return "markdown";
  }
  if (lower.endsWith(".ts") || lower.endsWith(".tsx")) {
    return "typescript";
  }
  if (lower.endsWith(".js") || lower.endsWith(".jsx")) {
    return "javascript";
  }
  if (lower.endsWith(".txt")) {
    return "plaintext";
  }
  return undefined;
}

interface ColumnDescriptor {
  readonly key: string;
  readonly label: string;
}

function resolveScriptTemplate(path: string, column: ColumnDescriptor | null): string {
  if (column || path.startsWith("columns/")) {
    const descriptor = column ?? {
      key: normalizeColumnKey(path.replace(/^columns\//, "").replace(/\.py$/, "")) || "column",
      label: column?.label ?? "Column",
    };
    return createColumnScriptTemplate(descriptor);
  }
  if (path === "startup.py") {
    return createStartupTemplate();
  }
  if (path === "run.py") {
    return createRunTemplate();
  }
  if (path === "table/transform.py") {
    return createTableTransformTemplate();
  }
  if (path === "table/validators.py") {
    return createTableValidatorsTemplate();
  }
  return createDefaultTemplate(path);
}

interface HarnessInputState {
  readonly header: string;
  readonly value: string;
  readonly quickTestColumn?: string;
}

function createEmptyHarnessInput(): HarnessInputState {
  return {
    header: "",
    value: "",
    quickTestColumn: "",
  };
}

function createColumnScriptTemplate(column: ColumnDescriptor): string {
  return `"""Derive the ${column.label} (${column.key}) column."""\n\n\ndef transform(value, *, row):\n    \"\"\"Adjust the value for persistence.\"\"\"\n    return value\n`;
}

function createStartupTemplate(): string {
  return `\"\"\"Startup hooks for this configuration.\"\"\"\n\n\ndef bootstrap(context):\n    \"\"\"Run once when the configuration loads.\"\"\"\n    # Add initialization logic here.\n`;
}

function createRunTemplate(): string {
  return `\"\"\"Entry point for document processing.\"\"\"\n\n\ndef run(document):\n    \"\"\"Yield transformed rows for the provided document.\"\"\"\n    yield document\n`;
}

function createTableTransformTemplate(): string {
  return `\"\"\"Row-level table transforms.\"\"\"\n\n\ndef transform(row):\n    \"\"\"Update the row before writing to the table.\"\"\"\n    return row\n`;
}

function createTableValidatorsTemplate(): string {
  return `\"\"\"Table validation hooks.\"\"\"\n\n\ndef validate(row):\n    \"\"\"Return a list of validation errors for the row.\"\"\"\n    return []\n`;
}

function createDefaultTemplate(path: string): string {
  return `\"\"\"Scaffold for ${path}.\"\"\"\n\n\n# Add implementation details here.\n`;
}

function normalizeColumnKey(input: string): string {
  const sanitized = input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return sanitized;
}

function createEmptyValidationState(): ValidationState {
  return { status: "idle", problems: [], response: null };
}

function createEmptyTestState(initial?: TestInputValues): TestState {
  return {
    status: "idle",
    lastDocumentId: initial?.documentId,
    lastNotes: initial?.notes,
  };
}

interface FunctionAnchor {
  readonly name: string;
  readonly line: number;
}

function extractFunctionAnchors(source: string): FunctionAnchor[] {
  const anchors: FunctionAnchor[] = [];
  const regex = /^\s*def\s+([a-zA-Z_][\w]*)\s*\(/gm;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(source)) !== null) {
    const preceding = source.slice(0, match.index);
    const line = preceding.split(/\n/).length;
    anchors.push({ name: match[1], line });
  }
  return anchors;
}

function formatSavedDescription(sha: string | null): string {
  if (!sha) {
    return "";
  }
  return `Saved ${sha.slice(0, 8)}`;
}

function formatValidationSummary(state: ValidationState): string {
  switch (state.status) {
    case "success":
      return state.ready ? "Validation passed" : "Validation reported issues";
    case "running":
      return "Running…";
    case "error":
      return "Validation failed";
    case "stale":
      return "Stale";
    default:
      return "Not run";
  }
}

function formatTestSummary(state: TestState): string {
  switch (state.status) {
    case "success":
      return state.response?.findings?.length ? "Completed with findings" : "Completed";
    case "running":
      return "Running…";
    case "error":
      return "Failed";
    case "stale":
      return "Stale";
    default:
      return "Not run";
  }
}

function formatConfidence(score: number | undefined): string {
  if (typeof score !== "number") {
    return "–";
  }
  return `${Math.round(score * 100)}%`;
}

function formatRelativeTime(value: string | Date | undefined | null): string {
  if (!value) {
    return "–";
  }
  const date = typeof value === "string" ? new Date(value) : value;
  const now = Date.now();
  const diff = now - date.getTime();
  const absDiff = Math.abs(diff);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (absDiff < minute) {
    return "just now";
  }
  if (absDiff < hour) {
    const minutes = Math.round(absDiff / minute);
    return diff >= 0 ? `${minutes}m ago` : `in ${minutes}m`;
  }
  if (absDiff < day) {
    const hours = Math.round(absDiff / hour);
    return diff >= 0 ? `${hours}h ago` : `in ${hours}h`;
  }
  const days = Math.round(absDiff / day);
  return diff >= 0 ? `${days}d ago` : `in ${days}d`;
}
