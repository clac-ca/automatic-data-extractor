import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useId,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { useQueryClient } from "@tanstack/react-query";
import Fuse from "fuse.js";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { Input } from "@ui/input";
import { CodeEditor, type CodeEditorHandle } from "@ui/code-editor";

import { useWorkspaceContext } from "../../workspaces.$workspaceId/WorkspaceContext";
import type { WorkspaceProfile } from "../../workspaces/workspaces-api";
import {
  activateVersion,
  archiveVersion,
  cloneVersion,
  composeManifestPatch,
  findActiveVersion,
  parseManifest,
  configsKeys,
  permanentlyDeleteVersion,
  restoreVersion,
  testVersion,
  useConfigManifestQuery,
  useConfigScriptsQuery,
  useConfigScriptQuery,
  useConfigVersionsQuery,
  useConfigsQuery,
  useCreateScriptMutation,
  usePatchManifestMutation,
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
import { useHotkeys } from "@shared/hooks/useHotkeys";
import { ApiError } from "@shared/api";

type ContextTab = "validate" | "test";

export const handle = { workspaceSectionId: "configurations" } as const;

type FileGroupKey = "core" | "columns" | "table" | "other";

interface TestInputValues {
  readonly documentId?: string;
  readonly notes?: string;
}

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

type ToastTone = "info" | "success" | "danger";

interface ToastMessage {
  readonly id: string;
  readonly tone: ToastTone;
  readonly title: string;
  readonly description?: string;
}

interface ConfirmDialogState {
  readonly tone: "info" | "danger";
  readonly title: string;
  readonly description?: string;
  readonly confirmLabel?: string;
  readonly cancelLabel?: string;
  readonly onConfirm: () => Promise<void> | void;
  readonly confirmTone?: "primary" | "danger";
}

const CORE_FILES = ["startup.py", "run.py"] as const;

export default function WorkspaceConfigEditorRoute() {
  const { workspace, workspaces } = useWorkspaceContext();
  const navigate = useNavigate();
  const params = useParams<{ configId: string; versionId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const configId = params.configId ?? "";
  const selectedVersionIdParam = params.versionId ?? "";
  const { toasts, pushToast, dismissToast } = useToastQueue();
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [fileFilter, setFileFilter] = useState<string>("");
  const [collapsedGroups, setCollapsedGroups] = useState<readonly FileGroupKey[]>([]);
  const [recentFilePaths, setRecentFilePaths] = useState<string[]>([]);
  const [quickSwitcherQuery, setQuickSwitcherQuery] = useState<string>("");
  const [contextTabs, setContextTabs] = useState<Record<string, ContextTab>>({});
  const [testInputs, setTestInputs] = useState<Record<string, TestInputValues>>({});

  useEffect(() => {
    setFileFilter("");
    setCollapsedGroups([]);
    setRecentFilePaths([]);
    setQuickSwitcherQuery("");
    setContextTabs({});
    setTestInputs({});
  }, [configId]);

  const handleConfirmDialog = useCallback(async () => {
    if (!confirmDialog) {
      return;
    }
    try {
      await confirmDialog.onConfirm();
      setConfirmDialog(null);
    } catch (error) {
      pushToast({
        tone: "danger",
        title: "Action failed",
        description: error instanceof Error ? error.message : "Unable to complete that action.",
      });
    }
  }, [confirmDialog, pushToast]);

  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });
  const configs = configsQuery.data ?? [];
  const activeConfig = useMemo(() => configs.find((config) => config.config_id === configId) ?? null, [configs, configId]);

  const includeArchived = searchParams.get("showArchived") === "1";
  const versionsQuery = useConfigVersionsQuery({
    workspaceId: workspace.id,
    configId,
    includeDeleted: includeArchived,
    enabled: Boolean(configId),
  });
  const versions = versionsQuery.data ?? [];
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
    () =>
      visibleVersions.find((version) => version.config_version_id === selectedVersionIdParam) ?? null,
    [selectedVersionIdParam, visibleVersions],
  );

  useEffect(() => {
    if (!configId) {
      return;
    }
    if (visibleVersions.length === 0) {
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

  useEffect(() => {
    if (!configId) {
      setContextTabs({});
      setTestInputs({});
      return;
    }
    const allowedVersionIds = new Set(orderedVersions.map((version) => version.config_version_id));
    setContextTabs((current) => {
      const filtered = Object.fromEntries(
        Object.entries(current).filter(([versionId]) => allowedVersionIds.has(versionId)),
      );
      return Object.keys(filtered).length === Object.keys(current).length ? current : filtered;
    });
    setTestInputs((current) => {
      const filtered = Object.fromEntries(
        Object.entries(current).filter(([versionId]) => allowedVersionIds.has(versionId)),
      );
      return Object.keys(filtered).length === Object.keys(current).length ? current : filtered;
    });
  }, [configId, orderedVersions]);

  const selectedVersionId = selectedVersion?.config_version_id ?? selectedVersionIdParam ?? "";
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

  useEffect(() => {
    setRecentFilePaths((current) =>
      current.filter((path) => fileEntries.some((entry) => entry.path === path)),
    );
  }, [fileEntries]);

  const requestedFilePath = searchParams.get("file");
  const selectedFilePath = useMemo(() => {
    if (requestedFilePath && fileEntries.some((entry) => entry.path === requestedFilePath)) {
      return requestedFilePath;
    }
    return fileEntries[0]?.path ?? "";
  }, [fileEntries, requestedFilePath]);

  useEffect(() => {
    const desired = selectedFilePath;
    const current = searchParams.get("file");
    if (!desired && !current) {
      return;
    }
    if (desired === current) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    if (desired) {
      next.set("file", desired);
    } else {
      next.delete("file");
    }
    setSearchParams(next, { replace: true });
  }, [searchParams, selectedFilePath, setSearchParams]);

  const {
    data: scriptContent,
    refetch: refetchScript,
    isLoading: isScriptLoadingInitial,
    isFetching: isScriptFetching,
  } = useConfigScriptQuery(
    workspace.id,
    configId,
    selectedVersionId,
    selectedFilePath,
    Boolean(selectedFilePath && selectedVersionId),
  );
  const isScriptLoading = useMemo(
    () => isScriptLoadingInitial || (isScriptFetching && !scriptContent),
    [isScriptFetching, isScriptLoadingInitial, scriptContent],
  );

  const selectedFileEntry = useMemo(
    () => fileEntries.find((entry) => entry.path === selectedFilePath) ?? null,
    [fileEntries, selectedFilePath],
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
  const languageLabel = useMemo(() => formatLanguageLabel(editorLanguage), [editorLanguage]);

  const selectFilePath = useCallback(
    (path: string) => {
      const next = new URLSearchParams(searchParams);
      if (path) {
        next.set("file", path);
      } else {
        next.delete("file");
      }
      setSearchParams(next, { replace: true });
      if (path) {
        setRecentFilePaths((current) => {
          const filtered = current.filter((value) => value !== path);
          return [path, ...filtered].slice(0, 20);
        });
      }
    },
    [searchParams, setSearchParams],
  );

  const handleFileFilterChange = useCallback(
    (value: string) => {
      setFileFilter(value);
    },
    [],
  );

  const handleToggleGroupCollapsed = useCallback(
    (group: FileGroupKey) => {
      setCollapsedGroups((previous) => {
        const exists = previous.includes(group);
        const next = exists ? previous.filter((value) => value !== group) : [...previous, group];
        return next;
      });
    },
    [],
  );

  const handleQuickSwitcherQueryChange = useCallback((value: string) => {
    setQuickSwitcherQuery(value);
  }, []);

  const createScript = useCreateScriptMutation(workspace.id, configId, selectedVersionId);
  const updateScript = useUpdateScriptMutation(workspace.id, configId, selectedVersionId);
  const patchManifest = usePatchManifestMutation(workspace.id, configId, selectedVersionId);

  const [editorValue, setEditorValue] = useState<string>("");
  const [currentSha, setCurrentSha] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [conflictDetected, setConflictDetected] = useState(false);
  const [lastSavedDescription, setLastSavedDescription] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!scriptContent) {
      setEditorValue("");
      setCurrentSha(null);
      setDirty(false);
      return;
    }
    setEditorValue(scriptContent.code);
    setCurrentSha(scriptContent.sha256);
    setDirty(false);
    setSaveError(null);
    setConflictDetected(false);
    setLastSavedDescription(formatSavedDescription(scriptContent.sha256));
  }, [scriptContent?.code, scriptContent?.sha256]);

  useEffect(() => {
    if (!dirty || isSaving || isActiveVersion || isArchivedVersion || conflictDetected || isScriptLoading) {
      return;
    }
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
    }
    saveTimer.current = setTimeout(() => {
      handlePersist();
    }, 1000);
    return () => {
      if (saveTimer.current) {
        clearTimeout(saveTimer.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    conflictDetected,
    currentSha,
    dirty,
    editorValue,
    isActiveVersion,
    isArchivedVersion,
    isSaving,
    isScriptLoading,
  ]);

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
    setIsSaving(true);
    setSaveError(null);
    try {
      const result = await updateScript.mutateAsync({
        path: selectedFilePath,
        code: editorValue,
        etag: currentSha,
      });
      setCurrentSha(result.sha256);
      setLastSavedDescription(formatSavedDescription(result.sha256));
      setDirty(false);
      setConflictDetected(false);
      queryClient.invalidateQueries({ queryKey: ["workspaces", workspace.id, "configs", configId] });
    } catch (error) {
      if (error instanceof ApiError && error.status === 412) {
        setConflictDetected(true);
        setSaveError("A newer version of this file exists. Reload to continue editing.");
      } else {
        setSaveError(error instanceof Error ? error.message : "Failed to save file.");
      }
    } finally {
      setIsSaving(false);
    }
  }, [
    configId,
    currentSha,
    editorValue,
    isActiveVersion,
    isArchivedVersion,
    isScriptLoading,
    queryClient,
    scriptContent,
    selectedFilePath,
    selectedVersionId,
    updateScript,
    workspace.id,
  ]);

  const handleReloadLatest = useCallback(() => {
    setConflictDetected(false);
    refetchScript();
  }, [refetchScript]);

  const [validationStates, setValidationStates] = useState<Record<string, ValidationState>>({});
  const [testStates, setTestStates] = useState<Record<string, TestState>>({});

  useEffect(() => {
    setValidationStates({});
    setTestStates({});
  }, [configId]);

  const defaultValidationState = useMemo(() => createEmptyValidationState(), []);
  const defaultTestState = useMemo(() => createEmptyTestState(), []);

  const validationState = selectedVersionId
    ? validationStates[selectedVersionId] ?? defaultValidationState
    : defaultValidationState;
  const testState = selectedVersionId ? testStates[selectedVersionId] ?? defaultTestState : defaultTestState;
  const testResponseFilesHash = testState.response?.files_hash ?? null;
  const activeContextTab = selectedVersionId ? contextTabs[selectedVersionId] ?? "validate" : "validate";

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
    const storedInput = testInputs[selectedVersionId];
    setTestStates((previous) => {
      if (previous[selectedVersionId]) {
        return previous;
      }
      return { ...previous, [selectedVersionId]: createEmptyTestState(storedInput) };
    });
  }, [selectedVersionId, testInputs]);

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    const storedInput = testInputs[selectedVersionId];
    if (!storedInput) {
      return;
    }
    setTestStates((previous) => {
      const current = previous[selectedVersionId];
      if (!current) {
        return previous;
      }
      if (current.status === "running") {
        return previous;
      }
      if (current.lastDocumentId === storedInput.documentId && current.lastNotes === storedInput.notes) {
        return previous;
      }
      return {
        ...previous,
        [selectedVersionId]: {
          ...current,
          lastDocumentId: storedInput.documentId,
          lastNotes: storedInput.notes,
        },
      };
    });
  }, [selectedVersionId, testInputs]);

  const setValidationStateForCurrent = useCallback(
    (next: ValidationState | ((previous: ValidationState) => ValidationState)) => {
      if (!selectedVersionId) {
        return;
      }
      setValidationStates((previous) => {
        const previousState = previous[selectedVersionId] ?? defaultValidationState;
        const resolvedState =
          typeof next === "function"
            ? (next as (prev: ValidationState) => ValidationState)(previousState)
            : next;
        if (previousState === resolvedState) {
          return previous[selectedVersionId] ? previous : { ...previous, [selectedVersionId]: resolvedState };
        }
        return { ...previous, [selectedVersionId]: resolvedState };
      });
    },
    [defaultValidationState, selectedVersionId],
  );

  const setTestStateForCurrent = useCallback(
    (next: TestState | ((previous: TestState) => TestState)) => {
      if (!selectedVersionId) {
        return;
      }
      setTestStates((previous) => {
        const previousState = previous[selectedVersionId] ?? defaultTestState;
        const resolvedState =
          typeof next === "function" ? (next as (prev: TestState) => TestState)(previousState) : next;
        if (previousState === resolvedState) {
          return previous[selectedVersionId] ? previous : { ...previous, [selectedVersionId]: resolvedState };
        }
        return { ...previous, [selectedVersionId]: resolvedState };
      });
    },
    [defaultTestState, selectedVersionId],
  );

  const markValidationStale = useCallback(() => {
    setValidationStateForCurrent((previous) =>
      previous.status === "success" ? { ...previous, status: "stale" } : previous,
    );
  }, [setValidationStateForCurrent]);

  const markTestStale = useCallback(() => {
    setTestStateForCurrent((previous) =>
      previous.status === "success" ? { ...previous, status: "stale" } : previous,
    );
  }, [setTestStateForCurrent]);

  const persistTestInput = useCallback(
    (documentId: string, notes?: string | null) => {
      if (!selectedVersionId) {
        return;
      }
      const trimmedNotes = notes?.trim();
      setTestInputs((previous) => {
        const nextInputs = { ...previous };
        if (!documentId && !trimmedNotes) {
          delete nextInputs[selectedVersionId];
        } else {
          nextInputs[selectedVersionId] = {
            documentId: documentId || undefined,
            notes: trimmedNotes || undefined,
          };
        }
        return nextInputs;
      });
    },
    [selectedVersionId],
  );

  const handleChangeContextTab = useCallback(
    (tab: ContextTab) => {
      if (!selectedVersionId) {
        return;
      }
      setContextTabs((previous) => {
        if (previous[selectedVersionId] === tab) {
          return previous;
        }
        return { ...previous, [selectedVersionId]: tab };
      });
    },
    [selectedVersionId],
  );

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    if (validationState.status === "success" && validationState.filesHash !== manifest.filesHash) {
      markValidationStale();
    }
  }, [
    manifest.filesHash,
    markValidationStale,
    selectedVersionId,
    validationState.filesHash,
    validationState.status,
  ]);

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    if (
      testState.status === "success" &&
      testResponseFilesHash &&
      testResponseFilesHash !== manifest.filesHash
    ) {
      markTestStale();
    }
  }, [
    manifest.filesHash,
    markTestStale,
    selectedVersionId,
    testResponseFilesHash,
    testState.status,
  ]);

  const handleValidate = useCallback(async () => {
    if (!selectedVersionId) return;
    setValidationStateForCurrent({ status: "running", problems: [], response: null });
    try {
      const result = await validateVersion(workspace.id, configId, selectedVersionId);
      setValidationStateForCurrent({
        status: "success",
        filesHash: result.files_hash,
        ready: result.ready,
        problems: result.problems,
        response: result,
        completedAt: new Date().toISOString(),
      });
    } catch (error) {
      setValidationStateForCurrent({
        status: "error",
        problems: [],
        message: error instanceof Error ? error.message : "Validation failed.",
        response: null,
        completedAt: new Date().toISOString(),
      });
    }
  }, [configId, selectedVersionId, setValidationStateForCurrent, workspace.id]);

  const handleTest = useCallback(
    async (documentId: string, notes?: string) => {
      if (!selectedVersionId) return;
      const trimmedNotes = notes?.trim();
      setTestStateForCurrent((previous) => ({
        ...previous,
        status: "running",
        message: undefined,
        lastDocumentId: documentId,
        lastNotes: trimmedNotes,
      }));
      persistTestInput(documentId, trimmedNotes);
      try {
        const result = await testVersion(
          workspace.id,
          configId,
          selectedVersionId,
          documentId,
          trimmedNotes ? trimmedNotes : undefined,
        );
        const completedAt = new Date().toISOString();
        setTestStateForCurrent((previous) => ({
          ...previous,
          status: "success",
          response: result,
          message: undefined,
          completedAt,
          responseCompletedAt: completedAt,
        }));
      } catch (error) {
        const completedAt = new Date().toISOString();
        setTestStateForCurrent((previous) => ({
          ...previous,
          status: "error",
          message: error instanceof Error ? error.message : "Test failed.",
          completedAt,
        }));
      }
    },
    [configId, persistTestInput, selectedVersionId, setTestStateForCurrent, workspace.id],
  );

  const handleSelectFile = useCallback(
    async (entry: FileEntry) => {
      selectFilePath(entry.path);
      if (entry.missing && !isActiveVersion && !isArchivedVersion) {
        const template = resolveScriptTemplate(entry.path, entry.column ?? null);
        const language = guessScriptLanguage(entry.path);
        try {
          await createScript.mutateAsync({
            path: entry.path,
            template: template ?? undefined,
            language,
          });
          await scriptsQuery.refetch();
          await refetchScript();
          markValidationStale();
          markTestStale();
        } catch (error) {
          console.error("Failed to scaffold file", error);
          pushToast({
            tone: "danger",
            title: "Unable to scaffold file",
            description: error instanceof Error ? error.message : "Failed to scaffold file.",
          });
        }
      }
    },
    [
      createScript,
      isActiveVersion,
      isArchivedVersion,
      refetchScript,
      markTestStale,
      markValidationStale,
      pushToast,
      selectFilePath,
      scriptsQuery,
    ],
  );

  const [isVersionDrawerOpen, setIsVersionDrawerOpen] = useState(false);
  const [saveAsNewTarget, setSaveAsNewTarget] = useState<ConfigVersionRecord | null>(null);
  const [isFilePaletteOpen, setIsFilePaletteOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const fileFilterInputRef = useRef<HTMLInputElement>(null);
  const codeEditorRef = useRef<CodeEditorHandle | null>(null);

  const handleOpenFilePalette = useCallback(() => {
    setIsCommandPaletteOpen(false);
    setIsFilePaletteOpen(true);
  }, []);

  const handleCloseFilePalette = useCallback(() => {
    setIsFilePaletteOpen(false);
  }, []);

  const handleOpenCommandPalette = useCallback(() => {
    setIsFilePaletteOpen(false);
    setIsCommandPaletteOpen(true);
  }, []);

  const handleCloseCommandPalette = useCallback(() => {
    setIsCommandPaletteOpen(false);
  }, []);

  const handleToggleFilePalette = useCallback(() => {
    setIsCommandPaletteOpen(false);
    setIsFilePaletteOpen((open) => !open);
  }, []);

  const handleToggleCommandPalette = useCallback(() => {
    setIsFilePaletteOpen(false);
    setIsCommandPaletteOpen((open) => !open);
  }, []);

  const focusFileRail = useCallback(() => {
    if (fileFilterInputRef.current) {
      fileFilterInputRef.current.focus();
      fileFilterInputRef.current.select();
    }
  }, []);

  const focusEditor = useCallback(() => {
    codeEditorRef.current?.focus();
  }, []);

  const handleOpenVersionsDrawerHotkey = useCallback(() => {
    setIsFilePaletteOpen(false);
    setIsCommandPaletteOpen(false);
    setIsVersionDrawerOpen(true);
  }, []);

  const handleSelectFromPalette = useCallback(
    (entry: FileEntry) => {
      setIsFilePaletteOpen(false);
      void handleSelectFile(entry);
    },
    [handleSelectFile],
  );

  const metaKeySymbol = useMetaKeySymbol();
  const quickSwitcherShortcutDisplay = metaKeySymbol === "⌘" ? "⌘P" : `${metaKeySymbol}+P`;
  const commandPaletteShortcut = metaKeySymbol === "⌘" ? "⌘⇧P" : `${metaKeySymbol}+Shift+P`;

  const handleFocusFileRailHotkey = useCallback(() => {
    handleCloseCommandPalette();
    handleCloseFilePalette();
    focusFileRail();
  }, [focusFileRail, handleCloseCommandPalette, handleCloseFilePalette]);

  const handleFocusEditorHotkey = useCallback(() => {
    handleCloseCommandPalette();
    handleCloseFilePalette();
    focusEditor();
  }, [focusEditor, handleCloseCommandPalette, handleCloseFilePalette]);

  const handlePrimaryActionHotkey = useCallback(() => {
    if (activeContextTab === "validate") {
      void handleValidate();
      return;
    }
    const lastDocumentId = testState.lastDocumentId;
    if (!lastDocumentId || testState.status === "running") {
      return;
    }
    void handleTest(lastDocumentId, testState.lastNotes);
  }, [activeContextTab, handleTest, handleValidate, testState.lastDocumentId, testState.lastNotes, testState.status]);

  const hotkeys = useMemo(
    () => [
      {
        combo: "meta+p",
        handler: handleToggleFilePalette,
        options: { allowInInputs: false },
      },
      {
        combo: "ctrl+p",
        handler: handleToggleFilePalette,
        options: { allowInInputs: false },
      },
      {
        combo: "meta+k",
        handler: handleToggleFilePalette,
        options: { allowInInputs: false },
      },
      {
        combo: "ctrl+k",
        handler: handleToggleFilePalette,
        options: { allowInInputs: false },
      },
      {
        combo: "meta+shift+p",
        handler: handleToggleCommandPalette,
        options: { allowInInputs: false },
      },
      {
        combo: "ctrl+shift+p",
        handler: handleToggleCommandPalette,
        options: { allowInInputs: false },
      },
      {
        combo: "g f",
        handler: handleFocusFileRailHotkey,
        options: { allowInInputs: false },
      },
      {
        combo: "g e",
        handler: handleFocusEditorHotkey,
        options: { allowInInputs: false },
      },
      {
        combo: "g v",
        handler: handleOpenVersionsDrawerHotkey,
        options: { allowInInputs: false },
      },
      {
        combo: "meta+enter",
        handler: handlePrimaryActionHotkey,
        options: { allowInInputs: true },
      },
      {
        combo: "ctrl+enter",
        handler: handlePrimaryActionHotkey,
        options: { allowInInputs: true },
      },
    ],
    [
      handleFocusEditorHotkey,
      handleFocusFileRailHotkey,
      handleOpenVersionsDrawerHotkey,
      handlePrimaryActionHotkey,
      handleToggleCommandPalette,
      handleToggleFilePalette,
    ],
  );

  useHotkeys(hotkeys);

  useEffect(() => {
    if ((!isFilePaletteOpen && !isCommandPaletteOpen) || typeof document === "undefined") {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isCommandPaletteOpen, isFilePaletteOpen]);

  const handleSwitchWorkspace = useCallback(
    (nextWorkspaceId: string) => {
      if (!nextWorkspaceId || nextWorkspaceId === workspace.id) {
        return;
      }
      navigate(`/workspaces/${nextWorkspaceId}/configs`);
    },
    [navigate, workspace.id],
  );

  const handleSwitchConfig = useCallback(
    (nextConfigId: string) => {
      if (!nextConfigId || nextConfigId === configId) {
        return;
      }
      navigate(`/workspaces/${workspace.id}/configs/${nextConfigId}/editor`);
    },
    [configId, navigate, workspace.id],
  );

  const handleSelectVersion = useCallback(
    (versionId: string) => {
      navigate(
        { pathname: versionId, search: searchParams.toString() },
        { replace: true, relative: "path" },
      );
      setIsVersionDrawerOpen(false);
    },
    [navigate, searchParams],
  );

  const handleToggleShowArchived = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    next.set("showArchived", includeArchived ? "0" : "1");
    setSearchParams(next, { replace: true });
  }, [includeArchived, searchParams, setSearchParams]);

  const invalidateConfigData = useCallback(() => {
    if (!configId) {
      return;
    }
    queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspace.id, configId) });
    queryClient.invalidateQueries({ queryKey: configsKeys.versions(workspace.id, configId, false) });
    queryClient.invalidateQueries({ queryKey: configsKeys.versions(workspace.id, configId, true) });
    queryClient.invalidateQueries({ queryKey: configsKeys.list(workspace.id, false) });
    queryClient.invalidateQueries({ queryKey: configsKeys.list(workspace.id, true) });
  }, [configId, queryClient, workspace.id]);

  const handleRequestSaveAsNewVersion = useCallback((version: ConfigVersionRecord) => {
    setSaveAsNewTarget(version);
    setIsVersionDrawerOpen(false);
  }, []);

  const handleConfirmSaveAsNewVersion = useCallback(
    async (input: SaveAsNewVersionInput) => {
      if (!saveAsNewTarget) {
        return;
      }
      try {
        const draft = await cloneVersion(workspace.id, configId, saveAsNewTarget.config_version_id, input);
        invalidateConfigData();
        await versionsQuery.refetch();
        handleSelectVersion(draft.config_version_id);
        setSaveAsNewTarget(null);
      } catch (error) {
        throw error instanceof Error ? error : new Error("Failed to save as new version.");
      }
    },
    [configId, handleSelectVersion, invalidateConfigData, saveAsNewTarget, versionsQuery, workspace.id],
  );

  const handleDismissSaveAsNewDialog = useCallback(() => setSaveAsNewTarget(null), []);

  const handleActivateVersion = useCallback(
    async (version: ConfigVersionRecord) => {
      try {
        await activateVersion(workspace.id, configId, version.config_version_id);
        invalidateConfigData();
        await versionsQuery.refetch();
        pushToast({
          tone: "success",
          title: `Activated ${version.semver}`,
          description: "This version is now live for new jobs.",
        });
      } catch (error) {
        pushToast({
          tone: "danger",
          title: "Activation failed",
          description: error instanceof Error ? error.message : "Failed to activate version.",
        });
      }
    },
    [configId, invalidateConfigData, pushToast, versionsQuery, workspace.id],
  );

  const handleArchiveVersion = useCallback(
    (version: ConfigVersionRecord) => {
      setConfirmDialog({
        tone: "danger",
        title: `Archive ${version.semver}`,
        description: "Archived versions stay accessible to existing jobs and can be restored at any time.",
        confirmLabel: "Archive",
        onConfirm: async () => {
          await archiveVersion(workspace.id, configId, version.config_version_id);
          invalidateConfigData();
          await versionsQuery.refetch();
          setIsVersionDrawerOpen(false);
          pushToast({
            tone: "info",
            title: `Archived ${version.semver}`,
            description: "The version is hidden from default views until restored.",
          });
        },
      });
    },
    [configId, invalidateConfigData, pushToast, versionsQuery, workspace.id],
  );

  const handleRestoreVersion = useCallback(
    (version: ConfigVersionRecord) => {
      setConfirmDialog({
        tone: "info",
        title: `Restore ${version.semver}`,
        description: "Restored versions appear in the drawer again and can be activated.",
        confirmLabel: "Restore",
        confirmTone: "primary",
        onConfirm: async () => {
          await restoreVersion(workspace.id, configId, version.config_version_id);
          invalidateConfigData();
          await versionsQuery.refetch();
          setIsVersionDrawerOpen(false);
          pushToast({
            tone: "success",
            title: `Restored ${version.semver}`,
          });
        },
      });
    },
    [configId, invalidateConfigData, pushToast, versionsQuery, workspace.id],
  );

  const handleDeleteVersion = useCallback(
    (version: ConfigVersionRecord) => {
      setConfirmDialog({
        tone: "danger",
        title: `Permanently delete ${version.semver}`,
        description:
          "This removes the version for everyone. Jobs that already reference it will retain read-only access.",
        confirmLabel: "Delete",
        onConfirm: async () => {
          await permanentlyDeleteVersion(workspace.id, configId, version.config_version_id);
          invalidateConfigData();
          await versionsQuery.refetch();
          setIsVersionDrawerOpen(false);
          pushToast({
            tone: "info",
            title: `Deleted ${version.semver}`,
            description: "The version has been removed permanently.",
          });
        },
      });
    },
    [configId, invalidateConfigData, pushToast, versionsQuery, workspace.id],
  );

  const [addColumnOpen, setAddColumnOpen] = useState(false);
  const [editingColumn, setEditingColumn] = useState<ManifestColumn | null>(null);
  const handleAddColumn = useCallback(
    async (column: ColumnDraft) => {
      const nextColumns = [...manifest.columns, columnToManifest(column, manifest.columns.length + 1)];
      try {
        await patchManifest.mutateAsync({
          manifest: { manifest: composeManifestPatch(manifest, nextColumns) },
          etag: manifestQuery.data?.etag ?? null,
        });
      } catch (error) {
        throw error instanceof Error ? error : new Error("Failed to add column.");
      }

      let scaffoldingError: Error | null = null;
      try {
        await createScript.mutateAsync({
          path: column.path,
          template: resolveScriptTemplate(column.path, column),
          language: guessScriptLanguage(column.path),
        });
      } catch (error) {
        scaffoldingError =
          error instanceof Error ? error : new Error("Column file was added, but scaffolding failed.");
      }

      await Promise.all([scriptsQuery.refetch(), manifestQuery.refetch()]);
      selectFilePath(column.path);
      markValidationStale();
      markTestStale();

      if (scaffoldingError) {
        throw scaffoldingError;
      }
    },
    [
      createScript,
      manifest,
      manifestQuery,
      markTestStale,
      markValidationStale,
      patchManifest,
      selectFilePath,
      scriptsQuery,
    ],
  );

  const handleReorderColumns = useCallback(
    async (orderedKeys: readonly string[]) => {
      const current = new Map(manifest.columns.map((entry) => [entry.key, entry] as const));
      const normalized = orderedKeys
        .map((key, index) => {
          const match = current.get(key);
          if (!match) {
            return null;
          }
          return { ...match, ordinal: index + 1 };
        })
        .filter((value): value is ManifestColumn => value !== null);
      try {
        await patchManifest.mutateAsync({
          manifest: { manifest: composeManifestPatch(manifest, normalized) },
          etag: manifestQuery.data?.etag ?? null,
        });
        await manifestQuery.refetch();
        markValidationStale();
        markTestStale();
      } catch (error) {
        pushToast({
          tone: "danger",
          title: "Reorder failed",
          description: error instanceof Error ? error.message : "Failed to reorder column.",
        });
      }
    },
    [manifest, manifestQuery, markTestStale, markValidationStale, patchManifest, pushToast],
  );

  const handleOpenColumnSettings = useCallback(
    (column: ManifestColumn) => {
      const latest = manifest.columns.find((entry) => entry.key === column.key);
      setEditingColumn(latest ?? column);
    },
    [manifest.columns],
  );

  const handleConfirmColumnSettings = useCallback(
    async (column: ManifestColumn, input: ColumnSettingsInput) => {
      const updatedColumns = manifest.columns.map((entry) =>
        entry.key === column.key
          ? {
              ...entry,
              label: input.label,
              required: input.required,
              enabled: input.enabled,
            }
          : entry,
      );

        try {
          await patchManifest.mutateAsync({
            manifest: { manifest: composeManifestPatch(manifest, updatedColumns) },
            etag: manifestQuery.data?.etag ?? null,
          });
          await manifestQuery.refetch();
          selectFilePath(column.path);
          markValidationStale();
          markTestStale();
        } catch (error) {
          throw error instanceof Error ? error : new Error("Failed to update column.");
        }
    },
    [manifest, manifestQuery, markTestStale, markValidationStale, patchManifest, selectFilePath],
  );

  const disableEditing = isActiveVersion || isArchivedVersion;
  const statusMessage = isScriptLoading
    ? "Loading file…"
    : disableEditing
      ? "Read-only"
      : isSaving
        ? "Saving…"
        : conflictDetected
          ? "Save failed"
          : dirty
            ? "Unsaved changes"
            : lastSavedDescription || "Saved";

  const handleEditorChange = useCallback(
    (nextValue: string) => {
      setEditorValue(nextValue);
      if (disableEditing || conflictDetected || isScriptLoading) {
        return;
      }
      setDirty(true);
      markValidationStale();
      markTestStale();
    },
    [conflictDetected, disableEditing, isScriptLoading, markTestStale, markValidationStale],
  );

  const allowSaveAsNew = Boolean(selectedVersion && isActiveVersion && !isArchivedVersion);
  const hasFreshTestResult = Boolean(
    testState.status === "success" &&
      testState.response?.files_hash &&
      testState.response.files_hash === manifest.filesHash,
  );
  const canActivateSelectedVersion = Boolean(
    selectedVersion &&
      !isActiveVersion &&
      !isArchivedVersion &&
      validationState.status === "success" &&
      validationState.ready &&
      hasFreshTestResult,
  );
  const saveAsNewHandler =
    allowSaveAsNew && selectedVersion ? () => handleRequestSaveAsNewVersion(selectedVersion) : undefined;

  const commandPaletteCommands = useMemo<CommandDefinition[]>(() => {
    const commands: CommandDefinition[] = [];

    commands.push({
      id: "open-file-quick-switcher",
      label: "Open file quick switcher",
      description: "Jump directly to any config file.",
      group: "Navigation",
      shortcut: quickSwitcherShortcutDisplay,
      disabled: fileEntries.length === 0,
      disabledReason: fileEntries.length === 0 ? "There are no files to open yet." : undefined,
      perform: handleOpenFilePalette,
      keywords: ["file", "jump", "search", "open"],
    });

    commands.push({
      id: "open-version-drawer",
      label: "Open version drawer",
      description: "Browse and manage configuration versions.",
      group: "Navigation",
      perform: () => setIsVersionDrawerOpen(true),
      keywords: ["version", "drawer", "history"],
    });

    commands.push({
      id: "toggle-archived-versions",
      label: includeArchived ? "Hide archived versions" : "Show archived versions",
      description: includeArchived
        ? "Hide archived versions from the drawer."
        : "Include archived versions in the drawer.",
      group: "Navigation",
      perform: handleToggleShowArchived,
      keywords: ["archive", "versions", "history"],
    });

    const validationRunning = validationState.status === "running";
    const testRunning = testState.status === "running";
    const lastDocumentId = testState.lastDocumentId ?? "";
    const lastTestNotes = testState.lastNotes;

    commands.push({
      id: "focus-validate-tab",
      label: "Focus Validate tab",
      description: "Show validation results in the context rail.",
      group: "Validation & testing",
      perform: () => handleChangeContextTab("validate"),
      keywords: ["validate", "sidebar", "context"],
    });

    commands.push({
      id: "run-validate",
      label: "Run Validate",
      description: "Check the selected version for structural issues.",
      group: "Validation & testing",
      disabled: !selectedVersion || validationRunning,
      disabledReason: !selectedVersion
        ? "Select a version to validate."
        : validationRunning
          ? "Validation already running."
          : undefined,
      perform: () => {
        if (!selectedVersion || validationRunning) {
          return;
        }
        handleChangeContextTab("validate");
        void handleValidate();
      },
      keywords: ["validate", "run", "check"],
    });

    commands.push({
      id: "focus-test-tab",
      label: "Focus Test tab",
      description: "Show testing tools in the context rail.",
      group: "Validation & testing",
      perform: () => handleChangeContextTab("test"),
      keywords: ["test", "sidebar", "context"],
    });

    commands.push({
      id: "rerun-test",
      label: "Re-run Test",
      description: lastDocumentId
        ? `Re-run Test with document ${lastDocumentId}.`
        : "Re-run the last test document.",
      group: "Validation & testing",
      disabled: !selectedVersion || testRunning || !lastDocumentId,
      disabledReason: !selectedVersion
        ? "Select a version to test."
        : testRunning
          ? "Test already running."
          : !lastDocumentId
            ? "Pick a document in the Test tab first."
            : undefined,
      perform: () => {
        if (!selectedVersion || testRunning || !lastDocumentId) {
          return;
        }
        handleChangeContextTab("test");
        void handleTest(lastDocumentId, lastTestNotes);
      },
      keywords: ["test", "run", "sample", "document"],
    });

    const saveDisabledReason = disableEditing
      ? "Switch to an inactive version to edit files."
      : isScriptLoading
        ? "Wait for the file to finish loading."
        : conflictDetected
          ? "Resolve the conflict before saving."
          : isSaving
            ? "Save in progress."
            : !dirty
              ? "No changes to save."
              : undefined;

    commands.push({
      id: "save-current-file",
      label: "Save current file",
      description: "Persist the current script changes.",
      group: "Editor",
      shortcut: metaKeySymbol === "⌘" ? "⌘S" : `${metaKeySymbol}+S`,
      disabled: Boolean(saveDisabledReason),
      disabledReason: saveDisabledReason,
      perform: () => {
        if (saveDisabledReason) {
          return;
        }
        void handlePersist();
      },
      keywords: ["save", "persist", "file"],
    });

    commands.push({
      id: "reload-latest",
      label: "Reload latest",
      description: "Discard local edits and fetch the latest file from the server.",
      group: "Editor",
      intent: "danger",
      disabled: !conflictDetected,
      disabledReason: conflictDetected ? undefined : "Reload is available after a save conflict.",
      perform: () => {
        if (!conflictDetected) {
          return;
        }
        handleReloadLatest();
      },
      keywords: ["reload", "conflict", "refresh"],
    });

    const saveAsNewDisabledReason = !selectedVersion
      ? "Select a version first."
      : allowSaveAsNew
        ? undefined
        : "Open the active version to clone it.";

    commands.push({
      id: "save-as-new-version",
      label: "Save as new version",
      description: "Clone the active version to start a new draft safely.",
      group: "Versions",
      disabled: Boolean(saveAsNewDisabledReason),
      disabledReason: saveAsNewDisabledReason,
      perform: () => {
        if (selectedVersion && allowSaveAsNew) {
          handleRequestSaveAsNewVersion(selectedVersion);
        }
      },
      keywords: ["save", "version", "clone"],
    });

    const activateDisabledReason = !selectedVersion
      ? "Select a version to activate."
      : isActiveVersion
        ? "This version is already active."
        : isArchivedVersion
          ? "Restore the version before activating it."
          : validationState.status !== "success" || !validationState.ready
            ? "Run Validate and resolve any problems first."
            : !hasFreshTestResult
              ? "Run Test for the current files hash first."
              : undefined;

    commands.push({
      id: "activate-version",
      label: "Activate this version",
      description: "Promote the selected version after Validate and Test succeed.",
      group: "Versions",
      disabled: Boolean(activateDisabledReason),
      disabledReason: activateDisabledReason,
      perform: () => {
        if (selectedVersion && !activateDisabledReason) {
          void handleActivateVersion(selectedVersion);
        }
      },
      keywords: ["activate", "promote", "version"],
    });

    if (selectedVersion && !isActiveVersion && !isArchivedVersion) {
      commands.push({
        id: "archive-version",
        label: "Archive this version",
        description: "Archive the selected version without deleting it.",
        group: "Versions",
        perform: () => handleArchiveVersion(selectedVersion),
        keywords: ["archive", "version"],
      });
    }

    if (selectedVersion && isArchivedVersion) {
      commands.push({
        id: "restore-version",
        label: "Restore this version",
        description: "Bring the archived version back for editing.",
        group: "Versions",
        perform: () => handleRestoreVersion(selectedVersion),
        keywords: ["restore", "archive", "version"],
      });
      commands.push({
        id: "delete-version",
        label: "Permanently delete this version",
        description: "Remove the archived version after confirmation.",
        group: "Versions",
        intent: "danger",
        perform: () => handleDeleteVersion(selectedVersion),
        keywords: ["delete", "archive", "version"],
      });
    }

    const addColumnDisabledReason = disableEditing
      ? "Switch to an inactive version to manage columns."
      : undefined;

    commands.push({
      id: "add-column",
      label: "Add column",
      description: "Create a new column and scaffold its script.",
      group: "Columns",
      disabled: Boolean(addColumnDisabledReason),
      disabledReason: addColumnDisabledReason,
      perform: () => {
        if (disableEditing) {
          return;
        }
        setAddColumnOpen(true);
      },
      keywords: ["column", "manifest", "add"],
    });

    if (selectedFileEntry?.column) {
      const column = selectedFileEntry.column;
      const columnLabel = column.label || column.key;
      const editColumnDisabledReason = disableEditing
        ? "Switch to an inactive version to edit column settings."
        : undefined;

      commands.push({
        id: "edit-column",
        label: `Edit column settings for ${columnLabel}`,
        description: "Adjust label, required, and enabled flags for the selected column.",
        group: "Columns",
        disabled: Boolean(editColumnDisabledReason),
        disabledReason: editColumnDisabledReason,
        perform: () => {
          if (disableEditing) {
            return;
          }
          setEditingColumn(column);
        },
        keywords: ["column", column.key, column.label ?? "", "settings", "manifest"],
      });
    }

    return commands;
  }, [
    allowSaveAsNew,
    conflictDetected,
    disableEditing,
    dirty,
    fileEntries.length,
    handleActivateVersion,
    handleArchiveVersion,
    handleChangeContextTab,
    handleDeleteVersion,
    handleOpenFilePalette,
    handlePersist,
    handleReloadLatest,
    handleRequestSaveAsNewVersion,
    handleRestoreVersion,
    handleTest,
    handleToggleShowArchived,
    handleValidate,
    hasFreshTestResult,
    includeArchived,
    isActiveVersion,
    isArchivedVersion,
    isSaving,
    isScriptLoading,
    metaKeySymbol,
    quickSwitcherShortcutDisplay,
    selectedFileEntry,
    selectedVersion,
    setAddColumnOpen,
    setEditingColumn,
    setIsVersionDrawerOpen,
    testState.lastDocumentId,
    testState.lastNotes,
    testState.status,
    validationState.ready,
    validationState.status,
  ]);

  const handleRunCommand = useCallback((command: CommandDefinition) => {
    setIsCommandPaletteOpen(false);
    try {
      const result = command.perform();
      if (result && typeof (result as Promise<unknown>).then === "function") {
        void (result as Promise<unknown>).catch((error) => {
          console.error("Command failed", error);
        });
      }
    } catch (error) {
      console.error("Command failed", error);
    }
  }, []);

  return (
    <div className="flex h-full flex-col gap-4">
      <EditorTopBar
        workspaces={workspaces}
        workspaceId={workspace.id}
        configs={configs}
        activeConfig={activeConfig}
        selectedVersion={selectedVersion}
        onSwitchWorkspace={handleSwitchWorkspace}
        onSwitchConfig={handleSwitchConfig}
        onToggleDrawer={() => setIsVersionDrawerOpen((value) => !value)}
        onSaveAsNew={saveAsNewHandler}
        onOpenCommandPalette={handleOpenCommandPalette}
        commandPaletteShortcut={commandPaletteShortcut}
        validationState={validationState}
        testState={testState}
        testReady={hasFreshTestResult}
      />

      <div className="flex min-h-0 flex-1 gap-4">
        <FileRail
          files={fileEntries}
          selectedPath={selectedFilePath}
          onSelect={handleSelectFile}
          onAddColumn={() => setAddColumnOpen(true)}
          disableInteractions={disableEditing}
          onReorderColumns={disableEditing ? undefined : handleReorderColumns}
          onEditColumn={disableEditing ? undefined : handleOpenColumnSettings}
          filter={fileFilter}
          onFilterChange={handleFileFilterChange}
          filterInputRef={fileFilterInputRef}
          collapsedGroups={collapsedGroups}
          onToggleGroup={handleToggleGroupCollapsed}
          onOpenQuickSwitcher={handleOpenFilePalette}
          quickSwitcherShortcut={metaKeySymbol}
        />

        <main className="flex min-w-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-white shadow-soft">
          <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3 text-sm">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-900">
                  {selectedFileEntry?.label ?? selectedFilePath ?? "Select a file"}
                </span>
                {currentSha ? (
                  <button
                    type="button"
                    className="text-[10px] uppercase tracking-wide text-slate-400 hover:text-slate-600"
                    onClick={() => {
                      if (typeof navigator !== "undefined" && navigator.clipboard) {
                        void navigator.clipboard.writeText(currentSha);
                        pushToast({
                          tone: "info",
                          title: "ETag copied",
                          description: currentSha,
                        });
                      }
                    }}
                    title="Copy file ETag"
                  >
                    ETag {currentSha.slice(0, 8)}
                  </button>
                ) : null}
              </div>
              {selectedFilePath ? (
                <span className="text-[11px] font-mono text-slate-400">{selectedFilePath}</span>
              ) : null}
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>{statusMessage}</span>
                {languageLabel ? (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {languageLabel}
                  </span>
                ) : null}
              </div>
            </div>
            {!disableEditing && (
              <Button
                size="sm"
                variant="ghost"
                disabled={isSaving || !dirty || isScriptLoading}
                onClick={handlePersist}
              >
                Save now
              </Button>
            )}
          </header>
          {isActiveVersion ? (
            <div className="flex items-center justify-between border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
              <span>This version is active and read-only. Save as new version to edit safely.</span>
              <Button size="sm" variant="secondary" onClick={saveAsNewHandler}>
                Save as new version
              </Button>
            </div>
          ) : null}

          {conflictDetected ? (
            <div className="border-b border-slate-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
              <div className="flex items-center justify-between">
                <span>{saveError ?? "This file changed on the server."}</span>
                <Button size="sm" variant="secondary" onClick={handleReloadLatest}>
                  Reload latest
                </Button>
              </div>
            </div>
          ) : saveError ? (
            <div className="border-b border-slate-200 bg-rose-50 px-4 py-2 text-sm text-rose-900">{saveError}</div>
          ) : null}

          <div className="flex-1 overflow-hidden rounded-b-2xl bg-slate-950">
            <CodeEditor
              ref={codeEditorRef}
              className="h-full"
              language={editorLanguage}
              value={editorValue}
              readOnly={disableEditing || conflictDetected || isScriptLoading}
              onChange={handleEditorChange}
              onSaveShortcut={
                disableEditing || conflictDetected || isScriptLoading ? undefined : handlePersist
              }
            />
          </div>
        </main>

        <ContextRail
          version={selectedVersion}
          isActiveVersion={isActiveVersion}
          activeTab={activeContextTab}
          onTabChange={handleChangeContextTab}
          onValidate={handleValidate}
          validationState={validationState}
          onActivate={selectedVersion ? () => handleActivateVersion(selectedVersion) : undefined}
          disableActivate={!canActivateSelectedVersion}
          onArchive={selectedVersion ? () => handleArchiveVersion(selectedVersion) : undefined}
          onRestore={selectedVersion ? () => handleRestoreVersion(selectedVersion) : undefined}
          onDelete={selectedVersion ? () => handleDeleteVersion(selectedVersion) : undefined}
          testState={testState}
          testReady={hasFreshTestResult}
          onTest={handleTest}
        />
      </div>

      <VersionDrawer
        open={isVersionDrawerOpen}
        onClose={() => setIsVersionDrawerOpen(false)}
        versions={orderedVersions}
        selectedVersionId={selectedVersionId}
        onPreview={handleSelectVersion}
        onActivate={handleActivateVersion}
        onSaveAsNewVersion={handleRequestSaveAsNewVersion}
        onArchive={handleArchiveVersion}
        onRestore={handleRestoreVersion}
        onDelete={handleDeleteVersion}
        onToggleShowArchived={handleToggleShowArchived}
        showArchived={includeArchived}
        validationStates={validationStates}
        testStates={testStates}
      />

      <FileQuickSwitcher
        open={isFilePaletteOpen}
        files={fileEntries}
        selectedPath={selectedFilePath}
        recentPaths={recentFilePaths}
        onClose={handleCloseFilePalette}
        onSelect={handleSelectFromPalette}
        shortcut={metaKeySymbol}
        initialQuery={quickSwitcherQuery}
        onQueryChange={handleQuickSwitcherQueryChange}
      />

      {addColumnOpen ? (
        <AddColumnDialog
          existingColumns={manifest.columns}
          existingPaths={fileEntries.map((entry) => entry.path)}
          onClose={() => setAddColumnOpen(false)}
          onConfirm={handleAddColumn}
        />
      ) : null}
      {editingColumn ? (
        <EditColumnDialog
          column={editingColumn}
          onCancel={() => setEditingColumn(null)}
          onConfirm={async (input) => {
            if (!editingColumn) {
              return;
            }
            await handleConfirmColumnSettings(editingColumn, input);
            setEditingColumn(null);
          }}
        />
      ) : null}
      {saveAsNewTarget ? (
        <SaveAsNewVersionDialog
          source={saveAsNewTarget}
          onCancel={handleDismissSaveAsNewDialog}
          onConfirm={handleConfirmSaveAsNewVersion}
        />
      ) : null}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
      <ConfirmDialog dialog={confirmDialog} onCancel={() => setConfirmDialog(null)} onConfirm={handleConfirmDialog} />
    </div>
  );
}

function useToastQueue() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const counter = useRef(0);

  const pushToast = useCallback(
    (toast: Omit<ToastMessage, "id">) => {
      const id = `toast-${Date.now()}-${counter.current++}`;
      setToasts((previous) => [...previous, { ...toast, id }]);
      return id;
    },
    [],
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== id));
  }, []);

  return { toasts, pushToast, dismissToast };
}

function ToastStack({
  toasts,
  onDismiss,
}: {
  readonly toasts: readonly ToastMessage[];
  readonly onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed top-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({
  toast,
  onDismiss,
}: {
  readonly toast: ToastMessage;
  readonly onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    const timeout = window.setTimeout(() => onDismiss(toast.id), 6000);
    return () => window.clearTimeout(timeout);
  }, [onDismiss, toast.id]);

  const toneClasses = (() => {
    switch (toast.tone) {
      case "success":
        return "border-emerald-200 bg-emerald-50 text-emerald-900";
      case "danger":
        return "border-rose-200 bg-rose-50 text-rose-900";
      default:
        return "border-slate-200 bg-white text-slate-900";
    }
  })();

  return (
    <div className={clsx("pointer-events-auto rounded-xl border px-4 py-3 shadow-lg", toneClasses)}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 text-sm">
          <p className="font-semibold">{toast.title}</p>
          {toast.description ? <p className="text-xs opacity-80">{toast.description}</p> : null}
        </div>
        <button
          type="button"
          className="text-xs font-semibold text-slate-500 hover:text-slate-700"
          onClick={() => onDismiss(toast.id)}
        >
          Close
        </button>
      </div>
    </div>
  );
}

function ConfirmDialog({
  dialog,
  onCancel,
  onConfirm,
}: {
  readonly dialog: ConfirmDialogState | null;
  readonly onCancel: () => void;
  readonly onConfirm: () => Promise<void>;
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!dialog) {
    return null;
  }

  const confirmTone = dialog.confirmTone ?? "danger";

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/30 backdrop-blur">
      <div className="w-[min(26rem,92vw)] space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
        <header className="space-y-1">
          <h2 className="text-base font-semibold text-slate-900">{dialog.title}</h2>
          {dialog.description ? <p className="text-xs text-slate-500">{dialog.description}</p> : null}
        </header>
        <div className="flex items-center justify-end gap-2 text-sm">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={isSubmitting}>
            {dialog.cancelLabel ?? "Cancel"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={confirmTone === "danger" ? "danger" : "primary"}
            onClick={async () => {
              setIsSubmitting(true);
              try {
                await onConfirm();
              } finally {
                setIsSubmitting(false);
              }
            }}
            disabled={isSubmitting}
          >
            {dialog.confirmLabel ?? "Confirm"}
          </Button>
        </div>
      </div>
    </div>
  );
}

interface EditorTopBarProps {
  readonly workspaces: readonly WorkspaceProfile[];
  readonly workspaceId: string;
  readonly configs: readonly ConfigRecord[];
  readonly activeConfig: ConfigRecord | null;
  readonly selectedVersion: ConfigVersionRecord | null;
  readonly onSwitchWorkspace: (workspaceId: string) => void;
  readonly onSwitchConfig: (configId: string) => void;
  readonly onToggleDrawer: () => void;
  readonly onSaveAsNew?: () => void;
  readonly onOpenCommandPalette: () => void;
  readonly commandPaletteShortcut: string;
  readonly validationState: ValidationState;
  readonly testState: TestState;
  readonly testReady: boolean;
}

function EditorTopBar({
  workspaces,
  workspaceId,
  configs,
  activeConfig,
  selectedVersion,
  onSwitchWorkspace,
  onSwitchConfig,
  onToggleDrawer,
  onSaveAsNew,
  onOpenCommandPalette,
  commandPaletteShortcut,
  validationState,
  testState,
  testReady,
}: EditorTopBarProps) {
  const versionState = getVersionState(selectedVersion);
  const validationSummary = getValidationStatusSummary(validationState);
  const testSummary = getTestStatusSummary(testState, { ready: testReady });
  const validationCompletedLabel = formatRelativeTime(validationState.completedAt);
  const testCompletedLabel = formatRelativeTime(testState.completedAt ?? testState.responseCompletedAt);

  const latestCompletedLabel = useMemo(() => {
    const entries: Array<{ timestamp: string; label: string | null }> = [];
    if (validationState.completedAt && validationCompletedLabel) {
      entries.push({ timestamp: validationState.completedAt, label: validationCompletedLabel });
    }
    const testTimestamp = testState.completedAt ?? testState.responseCompletedAt ?? null;
    if (testTimestamp && testCompletedLabel) {
      entries.push({ timestamp: testTimestamp, label: testCompletedLabel });
    }
    if (entries.length === 0) {
      return null;
    }
    entries.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    return entries[0]?.label ?? null;
  }, [
    testCompletedLabel,
    testState.completedAt,
    testState.responseCompletedAt,
    validationCompletedLabel,
    validationState.completedAt,
  ]);

  const validationText = validationSummary.label;
  const testText = testSummary.label === "Ready" ? "Tested" : testSummary.label;
  const healthSegments = [
    `${STATUS_TONE_ICONS[validationSummary.tone]} ${validationText}`,
    `${STATUS_TONE_ICONS[testSummary.tone]} ${testText}`,
  ];
  const healthText = latestCompletedLabel
    ? `${healthSegments.join(" • ")} • ${latestCompletedLabel}`
    : healthSegments.join(" • ");

  return (
    <header className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-soft">
      <div className="flex flex-1 items-center gap-3 text-sm">
        <select
          aria-label="Select workspace"
          className="focus-ring rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm"
          value={workspaceId}
          onChange={(event) => onSwitchWorkspace(event.target.value)}
        >
          {workspaces.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Select configuration"
          className="focus-ring rounded-lg border border-slate-200 bg-white px-3 py-1 text-sm"
          value={activeConfig?.config_id ?? ""}
          onChange={(event) => onSwitchConfig(event.target.value)}
        >
          {configs.map((config) => (
            <option key={config.config_id} value={config.config_id}>
              {config.title}
            </option>
          ))}
        </select>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="focus-ring inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:border-slate-300"
            onClick={onToggleDrawer}
          >
            <span className="text-[11px] uppercase tracking-wide text-slate-400">Version</span>
            <span className="text-sm font-semibold text-slate-900">{selectedVersion?.semver ?? "–"}</span>
            {versionState ? <VersionStatusBadge state={versionState} /> : null}
          </button>
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-600 normal-case">
            {healthText}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button size="sm" variant="ghost" onClick={onOpenCommandPalette}>
          <span className="flex items-center gap-2">
            <span>Quick actions</span>
            <span className="font-mono text-[11px] text-slate-400">{commandPaletteShortcut}</span>
          </span>
        </Button>
        <Button size="sm" variant="secondary" onClick={onToggleDrawer}>
          Manage versions
        </Button>
        {onSaveAsNew ? (
          <Button size="sm" onClick={onSaveAsNew}>
            Save as new version
          </Button>
        ) : null}
      </div>
    </header>
  );
}

interface FileRailProps {
  readonly files: readonly FileEntry[];
  readonly selectedPath: string;
  readonly onSelect: (file: FileEntry) => void;
  readonly onAddColumn: () => void;
  readonly disableInteractions?: boolean;
  readonly onReorderColumns?: (keys: readonly string[]) => void;
  readonly onEditColumn?: (column: ManifestColumn) => void;
  readonly filter: string;
  readonly onFilterChange: (value: string) => void;
  readonly filterInputRef?: RefObject<HTMLInputElement>;
  readonly collapsedGroups: readonly FileGroupKey[];
  readonly onToggleGroup: (group: FileGroupKey) => void;
  readonly onOpenQuickSwitcher: () => void;
  readonly quickSwitcherShortcut: string;
}

function FileRail({
  files,
  selectedPath,
  onSelect,
  onAddColumn,
  disableInteractions,
  onReorderColumns,
  onEditColumn,
  filter,
  onFilterChange,
  filterInputRef,
  collapsedGroups,
  onToggleGroup,
  onOpenQuickSwitcher,
  quickSwitcherShortcut,
}: FileRailProps) {
  const normalizedFilter = filter.trim().toLowerCase();
  const isFiltering = normalizedFilter.length > 0;
  const quickSwitcherDisplay = quickSwitcherShortcut === "⌘" ? "⌘P" : `${quickSwitcherShortcut}+P`;
  const hasAnyFiles = files.length > 0;
  const coreContentId = useId();
  const columnsContentId = useId();
  const tableContentId = useId();
  const otherContentId = useId();
  const groups = useMemo(() => {
    const match = (file: FileEntry) => matchesFileFilter(file, filter);
    const groupWithFilter = (group: FileGroupKey) => {
      const all = files.filter((file) => file.group === group);
      const visible = isFiltering ? all.filter(match) : all;
      return { all, visible };
    };
    return {
      core: groupWithFilter("core"),
      columns: groupWithFilter("columns"),
      table: groupWithFilter("table"),
      other: groupWithFilter("other"),
    };
  }, [files, filter, isFiltering]);

  const handleClearFilter = useCallback(() => {
    onFilterChange("");
  }, [onFilterChange]);

  return (
    <aside className="flex w-64 shrink-0 flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-3 shadow-soft">
      <div className="flex items-center gap-2">
        <Input
          ref={filterInputRef ?? undefined}
          value={filter}
          onChange={(event) => onFilterChange(event.target.value)}
          placeholder="Search files"
          className="h-9 flex-1"
        />
        {filter ? (
          <button
            type="button"
            className="focus-ring text-xs font-semibold text-slate-500 hover:text-slate-700"
            onClick={handleClearFilter}
          >
            Clear
          </button>
        ) : null}
      </div>

      <button
        type="button"
        className="focus-ring flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 hover:border-slate-300 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        onClick={onOpenQuickSwitcher}
        disabled={!hasAnyFiles}
      >
        <span>Jump to file</span>
        <span className="font-mono text-[11px] text-slate-400">{quickSwitcherDisplay}</span>
      </button>

      <FileGroup
        title="Core files"
        collapsed={collapsedGroups.includes("core")}
        onToggle={() => onToggleGroup("core")}
        contentId={coreContentId}
        hasFiles={groups.core.all.length > 0}
        isFiltering={isFiltering}
      >
        <FileList
          files={groups.core.visible}
          selectedPath={selectedPath}
          onSelect={onSelect}
          disableInteractions={disableInteractions}
          isFiltering={isFiltering}
          hasFiles={groups.core.all.length > 0}
          filterQuery={normalizedFilter}
        />
      </FileGroup>

      <FileGroup
        title="Columns"
        collapsed={collapsedGroups.includes("columns")}
        onToggle={() => onToggleGroup("columns")}
        actions={
          <button
            type="button"
            className="focus-ring rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-xs font-semibold text-slate-500"
            onClick={onAddColumn}
            disabled={disableInteractions}
          >
            + Add
          </button>
        }
        hasFiles={groups.columns.all.length > 0}
        isFiltering={isFiltering}
        contentId={columnsContentId}
      >
        {Boolean(onReorderColumns) && !isFiltering && !disableInteractions ? (
          <SortableColumnList
            files={groups.columns.all}
            selectedPath={selectedPath}
            onSelect={onSelect}
            onEditColumn={onEditColumn}
            onReorderColumns={onReorderColumns}
            disableInteractions={disableInteractions}
            listId={columnsContentId}
          />
        ) : (
          <FileList
            files={groups.columns.visible}
            selectedPath={selectedPath}
            onSelect={onSelect}
            disableInteractions={disableInteractions}
            isFiltering={isFiltering}
            hasFiles={groups.columns.all.length > 0}
            filterQuery={normalizedFilter}
            renderActions={
              onEditColumn
                ? (file) => {
                    if (!file.column) {
                      return null;
                    }
                    return (
                      <button
                        type="button"
                        className="rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 hover:border-slate-300"
                        disabled={disableInteractions}
                        onClick={(event) => {
                          event.stopPropagation();
                          onEditColumn(file.column!);
                        }}
                      >
                        Edit
                      </button>
                    );
                  }
                : undefined
            }
          />
        )}
      </FileGroup>

      <FileGroup
        title="Table"
        collapsed={collapsedGroups.includes("table")}
        onToggle={() => onToggleGroup("table")}
        contentId={tableContentId}
        hasFiles={groups.table.all.length > 0}
        isFiltering={isFiltering}
      >
        <FileList
          files={groups.table.visible}
          selectedPath={selectedPath}
          onSelect={onSelect}
          disableInteractions={disableInteractions}
          isFiltering={isFiltering}
          hasFiles={groups.table.all.length > 0}
          filterQuery={normalizedFilter}
        />
      </FileGroup>

      <FileGroup
        title="Other files"
        collapsed={collapsedGroups.includes("other")}
        onToggle={() => onToggleGroup("other")}
        contentId={otherContentId}
        hasFiles={groups.other.all.length > 0}
        isFiltering={isFiltering}
      >
        <FileList
          files={groups.other.visible}
          selectedPath={selectedPath}
          onSelect={onSelect}
          disableInteractions={disableInteractions}
          isFiltering={isFiltering}
          hasFiles={groups.other.all.length > 0}
          filterQuery={normalizedFilter}
        />
      </FileGroup>
    </aside>
  );
}

interface CommandDefinition {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly shortcut?: string;
  readonly group?: string;
  readonly keywords?: readonly string[];
  readonly disabled?: boolean;
  readonly disabledReason?: string;
  readonly intent?: "default" | "danger";
  readonly perform: () => void | Promise<void>;
}

interface CommandPaletteProps {
  readonly open: boolean;
  readonly commands: readonly CommandDefinition[];
  readonly onClose: () => void;
  readonly onRun: (command: CommandDefinition) => void;
  readonly shortcutDisplay: string;
}

interface CommandPaletteEntry {
  readonly command: CommandDefinition;
  readonly index: number;
  readonly score: number;
}

function CommandPalette({ open, commands, onClose, onRun, shortcutDisplay }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setHighlightedIndex(0);
      return;
    }
    const timeout = window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [open]);

  const normalizedQuery = query.trim().toLowerCase();

  const entries = useMemo<CommandPaletteEntry[]>(() => {
    const mapped = commands.map<CommandPaletteEntry>((command, index) => ({
      command,
      index,
      score: normalizedQuery ? scoreCommandMatch(command, normalizedQuery) : index,
    }));
    const filtered = normalizedQuery
      ? mapped.filter((entry) => Number.isFinite(entry.score))
      : mapped;
    if (!normalizedQuery) {
      return filtered;
    }
    return filtered.sort((a, b) =>
      a.score === b.score ? a.index - b.index : a.score - b.score,
    );
  }, [commands, normalizedQuery]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const firstEnabled = entries.findIndex((entry) => !entry.command.disabled);
    setHighlightedIndex(firstEnabled >= 0 ? firstEnabled : 0);
  }, [entries, open]);

  const moveHighlight = useCallback(
    (direction: 1 | -1) => {
      if (entries.length === 0) {
        return;
      }
      let nextIndex = highlightedIndex;
      for (let attempt = 0; attempt < entries.length; attempt += 1) {
        nextIndex = (nextIndex + direction + entries.length) % entries.length;
        if (!entries[nextIndex]?.command.disabled) {
          setHighlightedIndex(nextIndex);
          return;
        }
      }
      setHighlightedIndex(nextIndex);
    },
    [entries, highlightedIndex],
  );

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveHighlight(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        moveHighlight(-1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        const entry = entries[highlightedIndex];
        if (entry && !entry.command.disabled) {
          onRun(entry.command);
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    },
    [entries, highlightedIndex, moveHighlight, onClose, onRun],
  );

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 p-4"
      onClick={onClose}
    >
      <div
        className="mt-16 w-full max-w-xl rounded-2xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <header className="border-b border-slate-200 px-4 py-3">
          <Input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search commands"
            className="h-10 w-full"
          />
        </header>
        <div className="max-h-80 overflow-y-auto px-3 py-3">
          {entries.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-500">
              No commands found
            </div>
          ) : (
            <ul className="space-y-2">
              {entries.map((entry, index) => {
                const { command } = entry;
                const highlighted = index === highlightedIndex;
                const disabled = Boolean(command.disabled);
                const intent = command.intent ?? "default";
                const buttonClass = clsx(
                  "focus-ring w-full rounded-xl border px-3 py-2 text-left text-sm",
                  highlighted
                    ? "border-slate-900 bg-slate-900 text-white"
                    : disabled
                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                      : intent === "danger"
                        ? "border-rose-200 bg-white text-rose-600 hover:border-rose-300 hover:text-rose-700"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900",
                );
                const descriptionClass = highlighted
                  ? "mt-1 text-[11px] text-slate-200"
                  : "mt-1 text-[11px] text-slate-500";
                const disabledClass = highlighted
                  ? "mt-2 text-[11px] text-slate-300"
                  : "mt-2 text-[11px] text-slate-500";
                const groupBadge = command.group ? (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {command.group}
                  </span>
                ) : null;

                return (
                  <li key={command.id}>
                    <button
                      type="button"
                      className={buttonClass}
                      onClick={() => {
                        if (!disabled) {
                          onRun(command);
                        }
                      }}
                      disabled={disabled}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2">
                          {groupBadge}
                          <span
                            className={clsx(
                              "font-semibold",
                              highlighted
                                ? "text-white"
                                : intent === "danger"
                                  ? "text-rose-600"
                                  : "text-slate-900",
                            )}
                          >
                            {query
                              ? highlightQuery(command.label, query)
                              : command.label}
                          </span>
                        </span>
                        {command.shortcut ? (
                          <span className="font-mono text-[11px] text-slate-400">
                            {command.shortcut}
                          </span>
                        ) : null}
                      </div>
                      {command.description ? (
                        <p className={descriptionClass}>
                          {query ? highlightQuery(command.description, query) : command.description}
                        </p>
                      ) : null}
                      {command.disabledReason ? (
                        <p className={disabledClass}>{command.disabledReason}</p>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-2 text-[11px] text-slate-500">
          <span>Press Escape to close</span>
          <span className="font-mono text-slate-400">{shortcutDisplay}</span>
        </footer>
      </div>
    </div>
  );
}

interface FileQuickSwitcherProps {
  readonly open: boolean;
  readonly files: readonly FileEntry[];
  readonly selectedPath: string;
  readonly recentPaths: readonly string[];
  readonly onClose: () => void;
  readonly onSelect: (entry: FileEntry) => void;
  readonly shortcut: string;
  readonly initialQuery: string;
  readonly onQueryChange: (value: string) => void;
}

interface QuickSwitcherEntry {
  readonly file: FileEntry;
  readonly section?: string;
  readonly id: string;
}

function FileQuickSwitcher({
  open,
  files,
  selectedPath,
  recentPaths,
  onClose,
  onSelect,
  shortcut,
  initialQuery,
  onQueryChange,
}: FileQuickSwitcherProps) {
  const [query, setQuery] = useState(initialQuery);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listboxId = useId();
  const dialogTitleId = useId();
  const resultsSummaryId = useId();
  const trimmedQuery = query.trim();

  const fuse = useMemo(
    () =>
      new Fuse(files, {
        keys: ["label", "path", "column.key", "language"],
        threshold: 0.35,
        includeScore: true,
        ignoreLocation: true,
        minMatchCharLength: 2,
      }),
    [files],
  );

  const entries = useMemo<QuickSwitcherEntry[]>(() => {
    if (!trimmedQuery) {
      const seen = new Set<string>();
      const recentEntries: QuickSwitcherEntry[] = recentPaths
        .map((path) => files.find((file) => file.path === path))
        .filter((value): value is FileEntry => Boolean(value))
        .map((file) => {
          seen.add(file.path);
          return { file, section: "Recent", id: `quick-option-${file.id}` };
        });
      const remaining = files
        .filter((file) => !seen.has(file.path))
        .map((file) => ({
          file,
          section: recentEntries.length > 0 ? "All files" : undefined,
          id: `quick-option-${file.id}`,
        }));
      return [...recentEntries, ...remaining];
    }
    return fuse
      .search(trimmedQuery)
      .slice(0, 60)
      .map((result) => ({ file: result.item, id: `quick-option-${result.item.id}` }));
  }, [files, fuse, recentPaths, trimmedQuery]);

  const resultsSummary = entries.length === 0
    ? trimmedQuery
      ? "No files match the current search."
      : "No files available."
    : `${entries.length} ${entries.length === 1 ? "result" : "results"}, first is ${entries[0].file.label}.`;

  useEffect(() => {
    setHighlightedIndex((index) => {
      if (entries.length === 0) {
        return 0;
      }
      return Math.min(index, entries.length - 1);
    });
  }, [entries.length]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setQuery(initialQuery);
    setHighlightedIndex(0);
    const timeout = window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 0);
    return () => {
      window.clearTimeout(timeout);
    };
  }, [initialQuery, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    onQueryChange(query);
  }, [open, onQueryChange, query]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleFocusIn = (event: FocusEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(event.target as Node)) {
        event.stopPropagation();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("focusin", handleFocusIn);
    return () => document.removeEventListener("focusin", handleFocusIn);
  }, [open]);

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        if (entries.length === 0) {
          return;
        }
        setHighlightedIndex((index) => {
          const direction = event.shiftKey ? -1 : 1;
          const next = index + direction;
          if (next < 0) {
            return entries.length - 1;
          }
          if (next >= entries.length) {
            return 0;
          }
          return next;
        });
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setHighlightedIndex((index) =>
          entries.length === 0 ? 0 : Math.min(index + 1, entries.length - 1),
        );
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setHighlightedIndex((index) => Math.max(index - 1, 0));
        return;
      }
      if (event.key === "Home") {
        event.preventDefault();
        setHighlightedIndex(0);
        return;
      }
      if (event.key === "End") {
        event.preventDefault();
        setHighlightedIndex(entries.length > 0 ? entries.length - 1 : 0);
        return;
      }
      if (event.key === "PageDown") {
        event.preventDefault();
        setHighlightedIndex((index) =>
          entries.length === 0 ? 0 : Math.min(index + 5, entries.length - 1),
        );
        return;
      }
      if (event.key === "PageUp") {
        event.preventDefault();
        setHighlightedIndex((index) => Math.max(index - 5, 0));
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const chosen = entries[highlightedIndex];
        if (chosen) {
          onSelect(chosen.file);
        }
      }
    },
    [entries, highlightedIndex, onClose, onSelect],
  );

  if (!open) {
    return null;
  }

  const shortcutDisplay = shortcut === "⌘" ? "⌘P" : `${shortcut}+P`;
  const activeEntry = entries[highlightedIndex] ?? null;

  const handleSelect = (entry: QuickSwitcherEntry) => {
    onSelect(entry.file);
  };

  let lastSection: string | undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 px-6 py-16"
      role="dialog"
      aria-modal="true"
      aria-labelledby={dialogTitleId}
      aria-describedby={resultsSummaryId}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          event.preventDefault();
          onClose();
        }
      }}
      onKeyDown={handleKeyDown}
      ref={dialogRef}
    >
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <h2 id={dialogTitleId} className="sr-only">
          Jump to file
        </h2>
        <div className="border-b border-slate-200 p-3">
          <Input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search files by name, path, or language"
            className="h-10 w-full"
            aria-label="Search files"
          />
        </div>
        <p id={resultsSummaryId} className="sr-only" role="status" aria-live="polite">
          {resultsSummary}
        </p>
        <div className="max-h-80 overflow-y-auto p-2">
          {entries.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
              {trimmedQuery ? "No files match that search." : "No files to display."}
            </div>
          ) : (
            <ul
              className="flex flex-col gap-2"
              role="listbox"
              aria-activedescendant={activeEntry ? activeEntry.id : undefined}
              id={listboxId}
              ref={listRef}
            >
              {entries.map((entry, index) => {
                const file = entry.file;
                const highlighted = index === highlightedIndex;
                const selected = file.path === selectedPath;
                const languageLabel = formatLanguageLabel(file.language);
                const nodes: ReactNode[] = [];
                if (entry.section && entry.section !== lastSection) {
                  lastSection = entry.section;
                  nodes.push(
                    <li
                      key={`${entry.section}-heading`}
                      className="px-3 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400"
                      role="presentation"
                    >
                      {entry.section}
                    </li>,
                  );
                }
                const badgesContent: ReactNode[] = [];
                if (entry.section === "Recent" && !trimmedQuery) {
                  badgesContent.push(
                    <span
                      key="recent"
                      className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      Recent
                    </span>,
                  );
                }
                if (file.missing) {
                  badgesContent.push(
                    <span
                      key="missing"
                      className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      Missing
                    </span>,
                  );
                }
                if (file.disabled) {
                  badgesContent.push(
                    <span
                      key="disabled"
                      className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700"
                    >
                      Disabled
                    </span>,
                  );
                }
                if (languageLabel) {
                  badgesContent.push(
                    <span
                      key="language"
                      className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {languageLabel}
                    </span>,
                  );
                }
                nodes.push(
                  <li key={entry.id} role="presentation">
                    <button
                      type="button"
                      id={entry.id}
                      role="option"
                      aria-selected={highlighted}
                      className={clsx(
                        "focus-ring w-full rounded-xl border px-3 py-2 text-left text-sm",
                        highlighted
                          ? "border-slate-900 bg-slate-900 text-white"
                          : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900",
                      )}
                      onClick={() => handleSelect(entry)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-semibold">
                          {trimmedQuery ? highlightQuery(file.label, trimmedQuery) : file.label}
                        </span>
                        {badgesContent.length > 0 ? (
                          <span className="inline-flex flex-wrap items-center gap-1">{badgesContent}</span>
                        ) : null}
                      </div>
                      <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-slate-400">
                        <span className="truncate font-mono">
                          {trimmedQuery ? highlightQuery(file.path, trimmedQuery) : file.path}
                        </span>
                        {selected ? (
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                            Current
                          </span>
                        ) : null}
                      </div>
                      {file.column?.key ? (
                        <p className="mt-1 truncate text-[11px] text-slate-400">Column key: {file.column.key}</p>
                      ) : null}
                    </button>
                  </li>,
                );
                return nodes;
              })}
            </ul>
          )}
        </div>
        <footer className="flex items-center justify-between border-t border-slate-200 px-3 py-2 text-[11px] text-slate-500">
          <span>Press Tab to cycle, Enter to open, Escape to close</span>
          <span className="font-mono text-slate-400">{shortcutDisplay}</span>
        </footer>
      </div>
    </div>
  );
}

function FileGroup({
  title,
  collapsed,
  onToggle,
  actions,
  hasFiles,
  isFiltering,
  contentId,
  children,
}: {
  readonly title: string;
  readonly collapsed: boolean;
  readonly onToggle: () => void;
  readonly actions?: ReactNode;
  readonly hasFiles: boolean;
  readonly isFiltering: boolean;
  readonly contentId: string;
  readonly children: ReactNode;
}) {
  if (!hasFiles && !isFiltering && !actions) {
    return null;
  }

  return (
    <section>
      <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-400">
        <button
          type="button"
          className="focus-ring inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-controls={contentId}
        >
          <span aria-hidden>{collapsed ? "▸" : "▾"}</span>
          <span>{title}</span>
        </button>
        {actions}
      </div>
      <div id={contentId} hidden={collapsed} aria-hidden={collapsed}>
        {!collapsed ? children : null}
      </div>
    </section>
  );
}

interface SortableColumnListProps {
  readonly files: readonly FileEntry[];
  readonly selectedPath: string;
  readonly onSelect: (file: FileEntry) => void;
  readonly onEditColumn?: (column: ManifestColumn) => void;
  readonly onReorderColumns?: (keys: readonly string[]) => void;
  readonly disableInteractions?: boolean;
  readonly listId?: string;
}

function SortableColumnList({
  files,
  selectedPath,
  onSelect,
  onEditColumn,
  onReorderColumns,
  disableInteractions,
  listId,
}: SortableColumnListProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const itemIds = useMemo(() => files.map((file) => file.column?.key ?? file.id), [files]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (!onReorderColumns) {
        return;
      }
      const { active, over } = event;
      if (!over || active.id === over.id) {
        return;
      }
      const oldIndex = itemIds.findIndex((id) => id === active.id);
      const newIndex = itemIds.findIndex((id) => id === over.id);
      if (oldIndex === -1 || newIndex === -1) {
        return;
      }
      const reordered = arrayMove(files, oldIndex, newIndex);
      const keys = reordered
        .map((file) => file.column?.key)
        .filter((key): key is string => Boolean(key));
      onReorderColumns(keys);
    },
    [files, itemIds, onReorderColumns],
  );

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={itemIds} strategy={rectSortingStrategy}>
        <ul className="flex flex-col gap-2" id={listId}>
          {files.map((file) => (
            <SortableColumnItem
              key={file.path}
              file={file}
              selectedPath={selectedPath}
              onSelect={onSelect}
              onEditColumn={onEditColumn}
              disableInteractions={disableInteractions}
            />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}

interface SortableColumnItemProps {
  readonly file: FileEntry;
  readonly selectedPath: string;
  readonly onSelect: (file: FileEntry) => void;
  readonly onEditColumn?: (column: ManifestColumn) => void;
  readonly disableInteractions?: boolean;
}

function SortableColumnItem({
  file,
  selectedPath,
  onSelect,
  onEditColumn,
  disableInteractions,
}: SortableColumnItemProps) {
  const id = file.column?.key ?? file.id;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const selected = file.path === selectedPath;
  const badges: ReactNode[] = [];
  if (file.disabled) {
    badges.push(
      <span
        key="disabled"
        className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700"
      >
        Disabled
      </span>,
    );
  }
  if (file.missing) {
    badges.push(
      <span
        key="missing"
        className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
      >
        Scaffold
      </span>,
    );
  }
  const languageBadge = formatLanguageLabel(file.language);
  if (languageBadge) {
    badges.push(
      <span
        key={`language-${languageBadge}`}
        className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
      >
        {languageBadge}
      </span>,
    );
  }

  return (
    <li ref={setNodeRef} style={style}>
      <div
        className={clsx(
          "focus-ring group flex items-center gap-3 rounded-lg border px-3 py-2 text-xs",
          selected
            ? "border-slate-900 bg-slate-900 text-white"
            : file.missing
              ? "border-dashed border-slate-300 text-slate-500"
              : file.disabled
                ? "border-slate-200 bg-white text-slate-400"
                : "border-transparent bg-slate-50 text-slate-600 hover:border-slate-200",
          isDragging && "shadow-lg ring-2 ring-brand-200",
        )}
      >
        <button
          type="button"
          className="flex cursor-grab items-center text-slate-400 transition group-hover:text-slate-600"
          {...listeners}
          {...attributes}
          aria-label={`Reorder ${file.label}`}
        >
          ☰
        </button>
        <button
          type="button"
          className="flex-1 text-left"
          onClick={() => onSelect(file)}
          disabled={disableInteractions}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="truncate">{file.label}</span>
            {badges.length > 0 ? <span className="inline-flex items-center gap-1">{badges}</span> : null}
          </div>
          <p className="truncate text-[10px] text-slate-400">{file.path}</p>
          {file.column?.key ? (
            <p className="mt-1 truncate text-[10px] text-slate-400">Column key: {file.column.key}</p>
          ) : null}
        </button>
        {onEditColumn && file.column ? (
          <button
            type="button"
            className="rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 hover:border-slate-300"
            onClick={(event) => {
              event.stopPropagation();
              onEditColumn(file.column!);
            }}
            disabled={disableInteractions}
          >
            Edit
          </button>
        ) : null}
      </div>
    </li>
  );
}

interface FileListMeta {
  readonly index: number;
  readonly total: number;
  readonly disabled?: boolean;
}

function FileList({
  files,
  selectedPath,
  onSelect,
  disableInteractions,
  renderActions,
  isFiltering,
  hasFiles,
  filterQuery,
}: {
  readonly files: readonly FileEntry[];
  readonly selectedPath: string;
  readonly onSelect: (file: FileEntry) => void;
  readonly disableInteractions?: boolean;
  readonly renderActions?: (file: FileEntry, meta: FileListMeta) => ReactNode;
  readonly isFiltering?: boolean;
  readonly hasFiles?: boolean;
  readonly filterQuery?: string;
}) {
  if (files.length === 0) {
    const message = isFiltering && hasFiles ? "No matches" : "No files";
    return (
      <div className="rounded-lg border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-500">
        {message}
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {files.map((file, index) => {
        const selected = file.path === selectedPath;
        const badges: ReactNode[] = [];
        if (file.column?.required) {
          badges.push(
            <span
              key="required"
              className={clsx(
                "rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600 transition-opacity",
                isFiltering ? "opacity-100" : "opacity-0 group-hover:opacity-100",
              )}
            >
              Required
            </span>,
          );
        }
        if (file.disabled) {
          badges.push(
            <span
              key="disabled"
              className={clsx(
                "rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 transition-opacity",
                isFiltering ? "opacity-100" : "opacity-0 group-hover:opacity-100",
              )}
            >
              Disabled
            </span>,
          );
        }
        if (file.missing) {
          badges.push(
            <span
              key="missing"
              className="rounded-full border border-dashed border-slate-300 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
            >
              Scaffold
            </span>,
          );
        }
        const languageBadge = formatLanguageLabel(file.language);
        if (languageBadge) {
          badges.push(
            <span
              key={`language-${languageBadge}`}
              className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
            >
              {languageBadge}
            </span>,
          );
        }
        const actions = renderActions?.(file, { index, total: files.length, disabled: disableInteractions });
        return (
          <li key={file.path}>
            <button
              type="button"
              className={clsx(
                "group focus-ring w-full rounded-lg border px-3 py-2 text-left text-xs transition-colors",
                selected
                  ? "border-slate-900 bg-slate-900 text-white"
                  : file.missing
                    ? "border-dashed border-slate-300 text-slate-500"
                    : file.disabled
                      ? "border-slate-200 bg-white text-slate-400"
                      : "border-transparent bg-slate-50 text-slate-600 hover:border-slate-200",
              )}
              onClick={() => onSelect(file)}
              disabled={disableInteractions}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">
                  {filterQuery ? highlightQuery(file.label, filterQuery) : file.label}
                </span>
                {badges.length > 0 || actions ? (
                  <span className="inline-flex items-center gap-1">{badges}{actions}</span>
                ) : null}
              </div>
              <p className="truncate text-[10px] text-slate-400">
                {filterQuery ? highlightQuery(file.path, filterQuery) : file.path}
              </p>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function matchesFileFilter(file: FileEntry, filter: string): boolean {
  const trimmed = filter.trim().toLowerCase();
  if (!trimmed) {
    return true;
  }
  const languageValue = file.language?.toLowerCase() ?? "";
  const languageLabel = formatLanguageLabel(file.language)?.toLowerCase() ?? "";
  return (
    file.label.toLowerCase().includes(trimmed) ||
    file.path.toLowerCase().includes(trimmed) ||
    (file.column?.key ? file.column.key.toLowerCase().includes(trimmed) : false) ||
    (languageValue ? languageValue.includes(trimmed) : false) ||
    (languageLabel ? languageLabel.includes(trimmed) : false)
  );
}

function highlightQuery(text: string, query: string): ReactNode {
  const trimmed = query.trim();
  if (!trimmed) {
    return text;
  }
  const lowerText = text.toLowerCase();
  const lowerQuery = trimmed.toLowerCase();
  const length = trimmed.length;
  let position = 0;
  let matchIndex = lowerText.indexOf(lowerQuery, position);
  const parts: ReactNode[] = [];

  while (matchIndex !== -1) {
    if (matchIndex > position) {
      parts.push(text.slice(position, matchIndex));
    }
    const matched = text.slice(matchIndex, matchIndex + length);
    parts.push(
      <mark key={`highlight-${matchIndex}`} className="rounded bg-amber-100 px-0.5 text-amber-900">
        {matched}
      </mark>,
    );
    position = matchIndex + length;
    matchIndex = lowerText.indexOf(lowerQuery, position);
  }

  if (position < text.length) {
    parts.push(text.slice(position));
  }

  return parts.length > 0 ? parts : text;
}

function scoreFileMatch(file: FileEntry, normalizedQuery: string): number {
  const label = file.label.toLowerCase();
  const path = file.path.toLowerCase();
  const columnKey = file.column?.key?.toLowerCase() ?? "";
  const languageValue = file.language?.toLowerCase() ?? "";
  const languageLabel = formatLanguageLabel(file.language)?.toLowerCase() ?? "";
  const groupLabel = formatFileGroupLabel(file.group)?.toLowerCase() ?? "";

  if (
    label === normalizedQuery ||
    path === normalizedQuery ||
    columnKey === normalizedQuery ||
    languageValue === normalizedQuery ||
    languageLabel === normalizedQuery
  ) {
    return 0;
  }
  if (file.missing && normalizedQuery === "missing") {
    return 0.5;
  }
  if (file.disabled && normalizedQuery === "disabled") {
    return 0.5;
  }
  if (
    label.startsWith(normalizedQuery) ||
    path.startsWith(normalizedQuery) ||
    columnKey.startsWith(normalizedQuery)
  ) {
    return 1;
  }
  if (
    languageValue.startsWith(normalizedQuery) ||
    languageLabel.startsWith(normalizedQuery) ||
    (groupLabel && groupLabel.startsWith(normalizedQuery))
  ) {
    return 1.5;
  }
  if (label.includes(normalizedQuery) || path.includes(normalizedQuery) || columnKey.includes(normalizedQuery)) {
    return 2;
  }
  if (
    languageValue.includes(normalizedQuery) ||
    languageLabel.includes(normalizedQuery) ||
    (groupLabel && groupLabel.includes(normalizedQuery))
  ) {
    return 3;
  }
  return Number.POSITIVE_INFINITY;
}

function scoreCommandMatch(command: CommandDefinition, normalizedQuery: string): number {
  const candidates = [
    command.label,
    command.description ?? "",
    command.group ?? "",
    command.shortcut ?? "",
    command.disabledReason ?? "",
    ...(command.keywords ?? []),
  ]
    .map((value) => value.toLowerCase())
    .filter((value) => value.length > 0);

  if (candidates.some((value) => value === normalizedQuery)) {
    return 0;
  }
  if (candidates.some((value) => value.startsWith(normalizedQuery))) {
    return 1;
  }
  if (candidates.some((value) => value.includes(normalizedQuery))) {
    return 2;
  }
  return Number.POSITIVE_INFINITY;
}

function formatFileGroupLabel(group: FileGroupKey): string | null {
  switch (group) {
    case "core":
      return "Core";
    case "columns":
      return "Column";
    case "table":
      return "Table";
    case "other":
      return "Other";
    default:
      return null;
  }
}

function useMetaKeySymbol(): string {
  return useMemo(() => {
    if (typeof navigator === "undefined") {
      return "Ctrl";
    }
    return /Mac|iPhone|iPad|iPod/.test(navigator.platform) ? "⌘" : "Ctrl";
  }, []);
}

interface ContextRailProps {
  readonly version: ConfigVersionRecord | null;
  readonly isActiveVersion: boolean;
  readonly activeTab: ContextTab;
  readonly onTabChange: (tab: ContextTab) => void;
  readonly onValidate: () => void;
  readonly validationState: ValidationState;
  readonly onActivate?: () => void;
  readonly disableActivate: boolean;
  readonly onArchive?: () => void;
  readonly onRestore?: () => void;
  readonly onDelete?: () => void;
  readonly testState: TestState;
  readonly testReady: boolean;
  readonly onTest: (documentId: string, notes?: string) => void;
}

function ContextRail({
  version,
  isActiveVersion,
  activeTab,
  onTabChange,
  onValidate,
  validationState,
  onActivate,
  disableActivate,
  onArchive,
  onRestore,
  onDelete,
  testState,
  testReady,
  onTest,
}: ContextRailProps) {
  const [testDocumentId, setTestDocumentId] = useState("");
  const [testNotes, setTestNotes] = useState("");
  const versionState = getVersionState(version);
  const isArchived = versionState === "archived";
  const validationRunning = validationState.status === "running";
  const validationResponse = validationState.response ?? null;
  const findingsCount = testState.response?.findings.length ?? 0;
  const validationCompletedLabel = formatRelativeTime(validationState.completedAt);
  const validationCompletedTitle = formatAbsoluteTime(validationState.completedAt);
  const testCompletedLabel = formatRelativeTime(testState.completedAt);
  const testCompletedTitle = formatAbsoluteTime(testState.completedAt);
  const responseCompletedLabel = formatRelativeTime(testState.responseCompletedAt);
  const responseCompletedTitle = formatAbsoluteTime(testState.responseCompletedAt);
  const isTestRunning = testState.status === "running";
  const hasTestResponse = Boolean(testState.response);
  const disableTestRun = isTestRunning || testDocumentId.length === 0;
  const testSummary =
    testState.status === "success"
      ? testState.response?.summary ?? "Test complete."
      : testState.status === "running"
        ? testState.response?.summary ?? "Test running… showing last result."
        : testState.status === "stale"
          ? "Test results are stale after recent edits."
          : testState.status === "error"
            ? testState.response?.summary ?? "Last successful run."
            : testState.response?.summary ?? "Last test result.";
  const testSubtext =
    testState.status === "success"
      ? "Review the output before activating."
      : testState.status === "running"
        ? "A new test is in progress. Showing the most recent result until it finishes."
        : testState.status === "stale"
          ? "Run Test again to verify the latest changes."
          : testState.status === "error"
            ? "Latest test failed. Showing the most recent successful run."
            : "Most recent successful run is shown for reference.";
  const responseTimestampCopy = responseCompletedLabel
    ? testState.status === "success"
      ? `Test ran ${responseCompletedLabel}.`
      : testState.status === "running"
        ? `Last completed ${responseCompletedLabel}.`
        : `Last successful run ${responseCompletedLabel}.`
    : null;

  useEffect(() => {
    setTestDocumentId(testState.lastDocumentId ?? "");
    setTestNotes(testState.lastNotes ?? "");
  }, [testState.lastDocumentId, testState.lastNotes, version?.config_version_id]);

  if (!version) {
    return (
      <aside className="flex w-80 shrink-0 flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-soft text-sm">
        <p className="text-sm font-semibold text-slate-900">Select a version to manage actions.</p>
        <p className="text-xs text-slate-500">
          Choose a configuration version from the drawer to run Validate, Test, or Activate.
        </p>
      </aside>
    );
  }

  return (
    <aside className="flex w-80 shrink-0 flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-soft text-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Version</p>
          <p className="text-sm font-semibold text-slate-900">{version.semver}</p>
        </div>
        {versionState ? <VersionStatusBadge state={versionState} /> : null}
      </div>

      {isActiveVersion ? (
        <p className="text-[11px] text-slate-500">
          Active versions are read-only. Use <strong>Save as new version</strong> to begin editing safely.
        </p>
      ) : null}
      {isArchived ? (
        <p className="text-[11px] text-rose-600">
          Archived versions must be restored before they can be activated again.
        </p>
      ) : null}

      <div className="flex gap-2">
        <button
          type="button"
          className={clsx(
            "flex-1 rounded-lg border px-2 py-1 text-xs font-semibold",
            activeTab === "validate"
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-200 text-slate-600",
          )}
          onClick={() => onTabChange("validate")}
        >
          Validate
        </button>
        <button
          type="button"
          className={clsx(
            "flex-1 rounded-lg border px-2 py-1 text-xs font-semibold",
            activeTab === "test" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600",
          )}
          onClick={() => onTabChange("test")}
        >
          Test
        </button>
      </div>

      {activeTab === "validate" ? (
        <div className="space-y-3">
          <Button size="sm" onClick={onValidate} variant="secondary" disabled={validationRunning}>
            {validationRunning ? "Validating…" : "Run Validate"}
          </Button>
          {validationState.status === "success" ? (
            <Alert tone={validationState.ready ? "success" : "danger"}>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold">
                    {validationState.ready ? "Validation passed" : "Validation reported problems"}
                  </p>
                  <code className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">
                    {validationState.filesHash ?? "–"}
                  </code>
                </div>
                <p className="text-xs text-slate-600">
                  {validationState.ready
                    ? "Activate to promote this version to live."
                    : "Resolve the issues below before activating."}
                </p>
                {validationState.problems.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-4 text-xs">
                    {validationState.problems.map((problem) => (
                      <li key={problem}>{problem}</li>
                    ))}
                  </ul>
                ) : validationState.ready ? null : (
                  <p className="text-xs text-slate-600">No additional problem details were provided.</p>
                )}
                {validationCompletedLabel ? (
                  <p className="text-[11px] text-slate-400" title={validationCompletedTitle}>
                    Last validated {validationCompletedLabel}.
                  </p>
                ) : null}
              </div>
            </Alert>
          ) : validationState.status === "error" ? (
            <Alert tone="danger">
              <div className="space-y-1">
                <p>{validationState.message ?? "Validation failed."}</p>
                {validationCompletedLabel ? (
                  <p className="text-[11px] text-slate-400" title={validationCompletedTitle}>
                    Last attempted {validationCompletedLabel}.
                  </p>
                ) : null}
              </div>
            </Alert>
          ) : validationState.status === "stale" ? (
            <Alert tone="warning">
              <div className="space-y-1">
                <p>Validation is stale after recent edits. Run Validate again.</p>
                {validationCompletedLabel ? (
                  <p className="text-[11px] text-slate-400" title={validationCompletedTitle}>
                    Last validated {validationCompletedLabel}.
                  </p>
                ) : null}
              </div>
            </Alert>
          ) : null}

          {validationResponse ? (
            <details className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              <summary className="cursor-pointer font-semibold text-slate-700">View validation payload</summary>
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-white p-3 font-mono text-[11px] text-slate-700">
                {JSON.stringify(validationResponse, null, 2)}
              </pre>
            </details>
          ) : null}

          <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-600">
            <p className="text-xs font-semibold text-slate-700">Activation checklist</p>
            <ul className="space-y-1">
              <li className="flex items-center gap-2">
                <span className={validationState.ready ? "text-emerald-600" : "text-slate-400"}>
                  {validationState.ready ? "✅" : "○"}
                </span>
                <span>
                  {validationState.ready
                    ? "Validate passed on the latest files hash."
                    : "Run Validate and resolve any problems."}
                </span>
              </li>
              <li className="flex items-center gap-2">
                <span className={testReady ? "text-emerald-600" : "text-slate-400"}>{testReady ? "✅" : "○"}</span>
                <span>
                  {testReady
                    ? "Test matched the current files hash."
                    : "Run Test against the current files hash."}
                </span>
              </li>
            </ul>
          </div>
          <div className="space-y-2">
            <Button size="sm" onClick={onActivate} disabled={disableActivate || !onActivate}>
              Activate
            </Button>
            <p className="text-[11px] text-slate-500">Promote this version to be the active configuration.</p>
          </div>

          <div className="space-y-2 text-xs">
            {!isArchived && onArchive ? (
              <Button size="sm" variant="secondary" onClick={onArchive} disabled={isActiveVersion}>
                Archive
              </Button>
            ) : null}
            {isArchived && onRestore ? (
              <Button size="sm" variant="secondary" onClick={onRestore}>
                Restore
              </Button>
            ) : null}
            {isArchived && onDelete ? (
              <Button size="sm" variant="danger" onClick={onDelete}>
                Permanently delete
              </Button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <Input
            value={testDocumentId}
            onChange={(event) => setTestDocumentId(event.target.value)}
            placeholder="Document ID"
          />
          <textarea
            value={testNotes}
            onChange={(event) => setTestNotes(event.target.value)}
            className="h-24 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
            placeholder="Notes for this test run (optional)"
          />
          <Button size="sm" onClick={() => onTest(testDocumentId, testNotes)} disabled={disableTestRun}>
            {isTestRunning ? "Running…" : "Run Test"}
          </Button>
          {isTestRunning && !hasTestResponse ? (
            <Alert tone="info">Test running… results will appear here once the sample finishes processing.</Alert>
          ) : null}
          {testState.status === "stale" ? (
            <Alert tone="warning">
              <div className="space-y-1">
                <p>Test results are stale after recent edits. Run Test again to verify the latest changes.</p>
                {responseCompletedLabel ? (
                  <p className="text-[11px] text-slate-400" title={responseCompletedTitle}>
                    Last successful run {responseCompletedLabel}.
                  </p>
                ) : null}
              </div>
            </Alert>
          ) : null}
          {testState.status === "error" ? (
            <Alert tone="danger">
              <div className="space-y-1">
                <p>{testState.message ?? "Test failed."}</p>
                {testCompletedLabel ? (
                  <p className="text-[11px] text-slate-400" title={testCompletedTitle}>
                    Last attempted {testCompletedLabel}.
                  </p>
                ) : null}
              </div>
            </Alert>
          ) : null}
          {hasTestResponse ? (
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
              <div className="space-y-2">
                <p className="font-semibold text-slate-800">{testSummary}</p>
                <p className="text-xs text-slate-600">{testSubtext}</p>
                <dl className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span>Document</span>
                    <span className="font-mono text-[11px] text-slate-600">{testState.response?.document_id ?? "–"}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span>Files hash</span>
                    <code className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-white">
                      {testState.response?.files_hash ?? "–"}
                    </code>
                  </div>
                </dl>
                {findingsCount > 0 ? (
                  <div>
                    <p className="font-semibold text-slate-800">Findings</p>
                    <ul className="mt-1 list-disc space-y-1 pl-4">
                      {testState.response?.findings.map((finding) => (
                        <li key={finding}>{finding}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="text-slate-600">No findings were reported.</p>
                )}
                {responseTimestampCopy ? (
                  <p className="text-[11px] text-slate-400" title={responseCompletedTitle}>
                    {responseTimestampCopy}
                  </p>
                ) : null}
              </div>
              {testState.response ? (
                <details className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-[11px] text-slate-700">
                  <summary className="cursor-pointer font-semibold text-slate-700">View test payload</summary>
                  <pre className="mt-1 max-h-48 overflow-auto font-mono">
                    {JSON.stringify(testState.response, null, 2)}
                  </pre>
                </details>
              ) : null}
            </div>
          ) : null}
          {!hasTestResponse && !isTestRunning && testState.status !== "error" ? (
            <p className="text-xs text-slate-500">Run Test with a sample document to preview extraction results.</p>
          ) : null}
        </div>
      )}
    </aside>
  );
}

interface VersionDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly versions: readonly ConfigVersionRecord[];
  readonly selectedVersionId: string;
  readonly onPreview: (versionId: string) => void;
  readonly onActivate: (version: ConfigVersionRecord) => void;
  readonly onSaveAsNewVersion: (version: ConfigVersionRecord) => void;
  readonly onArchive: (version: ConfigVersionRecord) => void;
  readonly onRestore: (version: ConfigVersionRecord) => void;
  readonly onDelete: (version: ConfigVersionRecord) => void;
  readonly onToggleShowArchived: () => void;
  readonly showArchived: boolean;
  readonly validationStates: Readonly<Record<string, ValidationState>>;
  readonly testStates: Readonly<Record<string, TestState>>;
}

function VersionDrawer({
  open,
  onClose,
  versions,
  selectedVersionId,
  onPreview,
  onActivate,
  onSaveAsNewVersion,
  onArchive,
  onRestore,
  onDelete,
  onToggleShowArchived,
  showArchived,
  validationStates,
  testStates,
}: VersionDrawerProps) {
  const hasArchivedVersions = versions.some((version) => Boolean(version.deleted_at));

  return (
    <div
      className={clsx(
        "pointer-events-none fixed inset-0 z-40 flex justify-end transition",
        open ? "pointer-events-auto" : "opacity-0",
      )}
    >
      <div className="flex-1" onClick={onClose} aria-hidden />
      <aside
        className={clsx(
          "flex h-full w-[min(28rem,92vw)] flex-col border-l border-slate-200 bg-white shadow-2xl transition",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Versions</h2>
            <p className="text-xs text-slate-500">Manage activation state and history.</p>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </header>
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Archive filter</p>
            <p className="text-xs text-slate-500">
              {showArchived
                ? "Archived versions are visible in this list."
                : hasArchivedVersions
                  ? "Archived versions are hidden to reduce noise."
                  : "No archived versions yet."}
            </p>
          </div>
          <Button size="sm" variant={showArchived ? "secondary" : "ghost"} onClick={onToggleShowArchived}>
            {showArchived ? "Hide archived" : "Show archived"}
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {versions.length === 0 ? (
            <p className="text-xs text-slate-500">No versions yet.</p>
          ) : (
            <div className="space-y-4">
              {versions.map((version, index) => {
                const isSelected = version.config_version_id === selectedVersionId;
                const state = getVersionState(version);
                const isActive = state === "active";
                const isArchived = state === "archived";
                const createdLabel = formatRelativeTime(version.created_at);
                const activatedLabel = formatRelativeTime(version.activated_at);
                const archivedLabel = formatRelativeTime(version.deleted_at);
                const createdTitle = formatAbsoluteTime(version.created_at);
                const activatedTitle = formatAbsoluteTime(version.activated_at);
                const archivedTitle = formatAbsoluteTime(version.deleted_at);
                const validationState = validationStates[version.config_version_id];
                const testStateForVersion = testStates[version.config_version_id];
                const validationSummary = getValidationStatusSummary(validationState);
                const testSummary = getTestStatusSummary(testStateForVersion);
                const validationCompletedLabel = formatRelativeTime(validationState?.completedAt);
                const validationCompletedTitle = formatAbsoluteTime(validationState?.completedAt);
                const testCompletedLabel = formatRelativeTime(
                  testStateForVersion?.completedAt ?? testStateForVersion?.responseCompletedAt,
                );
                const testCompletedTitle = formatAbsoluteTime(
                  testStateForVersion?.completedAt ?? testStateForVersion?.responseCompletedAt,
                );

                return (
                  <div key={version.config_version_id} className="flex gap-3">
                    <div className="flex w-6 flex-col items-center">
                      <span
                        className={clsx(
                          "mt-3 h-2 w-2 rounded-full border-2",
                          isSelected ? "border-slate-900 bg-slate-900" : "border-slate-300 bg-white",
                        )}
                        aria-hidden
                      />
                      {index < versions.length - 1 ? (
                        <span className="mt-1 flex-1 w-px bg-slate-200" aria-hidden />
                      ) : null}
                    </div>
                    <article
                      className={clsx(
                        "flex-1 rounded-2xl border p-3 text-left text-sm transition",
                        isSelected
                          ? "border-slate-900 shadow-lg"
                          : "border-slate-200 bg-white hover:border-slate-300",
                      )}
                    >
                      <header className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-sm font-semibold text-slate-900">{version.semver}</p>
                          <div className="space-y-1 text-xs text-slate-500">
                            <p title={createdTitle}>Created {createdLabel ?? createdTitle ?? "–"}</p>
                            {version.created_by ? (
                              <p className="text-[11px] text-slate-400">By {version.created_by}</p>
                            ) : null}
                            {version.activated_at ? (
                              <p title={activatedTitle}>Activated {activatedLabel ?? activatedTitle ?? "–"}</p>
                            ) : null}
                            {version.deleted_at ? (
                              <p className="text-[11px] text-rose-600" title={archivedTitle}>
                                Archived {archivedLabel ?? archivedTitle ?? "–"}
                                {version.deleted_by ? (
                                  <span className="text-rose-500"> by {version.deleted_by}</span>
                                ) : null}
                              </p>
                            ) : null}
                          </div>
                        </div>
                        {state ? <VersionStatusBadge state={state} /> : null}
                      </header>

                      {version.message ? (
                        <p className="mt-3 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">{version.message}</p>
                      ) : null}

                      <dl className="mt-3 space-y-1 text-xs text-slate-500">
                        <div className="flex items-center justify-between gap-2">
                          <span>Files hash</span>
                          <code className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-700">
                            {version.files_hash}
                          </code>
                        </div>
                      </dl>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <RunStatusBadge
                          kind="Validate"
                          summary={validationSummary}
                          completedLabel={validationCompletedLabel}
                          title={validationCompletedTitle}
                        />
                        <RunStatusBadge
                          kind="Test"
                          summary={testSummary}
                          completedLabel={testCompletedLabel}
                          title={testCompletedTitle}
                        />
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => onPreview(version.config_version_id)}
                          disabled={isSelected}
                        >
                          {isSelected ? "Viewing" : "Preview"}
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => onActivate(version)}
                          disabled={!onActivate || isActive || isArchived}
                        >
                          Activate
                        </Button>
                        {isActive ? (
                          <Button size="sm" variant="secondary" onClick={() => onSaveAsNewVersion(version)}>
                            Save as new version
                          </Button>
                        ) : null}
                        {!isArchived ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => onArchive(version)}
                            disabled={isActive}
                          >
                            Archive
                          </Button>
                        ) : (
                          <>
                            <Button size="sm" variant="secondary" onClick={() => onRestore(version)}>
                              Restore
                            </Button>
                            <Button size="sm" variant="danger" onClick={() => onDelete(version)}>
                              Permanently delete
                            </Button>
                          </>
                        )}
                      </div>
                    </article>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
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
            Clone <span className="font-semibold text-slate-700">{source.semver ?? "unspecified"}</span> into a new inactive
            version so you can make edits safely.
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
            Release note (optional)
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

interface ColumnDraft {
  readonly key: string;
  readonly label: string;
  readonly required: boolean;
  readonly path: string;
}

function columnToManifest(column: ColumnDraft, ordinal: number): ManifestColumn {
  return {
    key: column.key,
    label: column.label,
    path: column.path,
    ordinal,
    required: column.required,
    enabled: true,
    depends_on: [],
  };
}

function normalizeColumnKey(input: string): string {
  const sanitized = input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return sanitized;
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

function createColumnScriptTemplate(column: ColumnDescriptor): string {
  return `"""Derive the ${column.label} (${column.key}) column."""


def transform(value, *, row):
    """Adjust the value for persistence."""
    return value
`;
}

function createStartupTemplate(): string {
  return `"""Startup hooks for this configuration."""


def bootstrap(context):
    """Run once when the configuration loads."""
    # Add initialization logic here.
`;
}

function createRunTemplate(): string {
  return `"""Entry point for document processing."""


def run(document):
    """Yield transformed rows for the provided document."""
    yield document
`;
}

function createTableTransformTemplate(): string {
  return `"""Row-level table transforms."""


def transform(row):
    """Update the row before writing to the table."""
    return row
`;
}

function createTableValidatorsTemplate(): string {
  return `"""Table validation hooks."""


def validate(row):
    """Return a list of validation errors for the row."""
    return []
`;
}

function createDefaultTemplate(path: string): string {
  return `"""Scaffold for ${path}."""


# Add implementation details here.
`;
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

function formatLanguageLabel(language?: string | null): string | null {
  if (!language) {
    return null;
  }
  const normalized = language.toLowerCase();
  switch (normalized) {
    case "python":
      return "Python";
    case "json":
      return "JSON";
    case "yaml":
    case "yml":
      return "YAML";
    case "sql":
      return "SQL";
    case "jinja":
    case "jinja2":
    case "j2":
      return "Jinja";
    case "markdown":
    case "md":
      return "Markdown";
    case "typescript":
      return "TypeScript";
    case "javascript":
      return "JavaScript";
    case "plaintext":
    case "text":
      return "Plain text";
    case "tsx":
      return "TSX";
    case "jsx":
      return "JSX";
    default:
      return language;
  }
}

function formatSavedDescription(sha: string) {
  void sha;
  return "Saved";
}

function formatRelativeTime(timestamp?: string | null) {
  if (!timestamp) {
    return null;
  }
  const value = Date.parse(timestamp);
  if (Number.isNaN(value)) {
    return null;
  }
  const diff = Date.now() - value;
  if (diff < 0) {
    return "just now";
  }
  const seconds = Math.round(diff / 1000);
  if (seconds < 5) {
    return "just now";
  }
  if (seconds < 60) {
    return `${seconds} second${seconds === 1 ? "" : "s"} ago`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.round(hours / 24);
  if (days < 7) {
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }
  const weeks = Math.round(days / 7);
  if (weeks < 5) {
    return `${weeks} week${weeks === 1 ? "" : "s"} ago`;
  }
  const months = Math.round(days / 30);
  if (months < 12) {
    return `${months} month${months === 1 ? "" : "s"} ago`;
  }
  const years = Math.round(days / 365);
  return `${years} year${years === 1 ? "" : "s"} ago`;
}

function formatAbsoluteTime(timestamp?: string | null) {
  if (!timestamp) {
    return undefined;
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toLocaleString();
}

interface AddColumnDialogProps {
  readonly existingColumns: readonly ManifestColumn[];
  readonly existingPaths: readonly string[];
  readonly onClose: () => void;
  readonly onConfirm: (column: ColumnDraft) => Promise<void>;
}

function AddColumnDialog({ existingColumns, existingPaths, onClose, onConfirm }: AddColumnDialogProps) {
  const [keyInput, setKeyInput] = useState("");
  const [label, setLabel] = useState("");
  const [required, setRequired] = useState(true);
  const [keyEdited, setKeyEdited] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (keyEdited || keyInput.trim().length > 0) {
      return;
    }
    const suggestion = normalizeColumnKey(label);
    if (suggestion !== keyInput) {
      setKeyInput(suggestion);
    }
  }, [keyEdited, keyInput, label]);

  const normalizedKey = useMemo(() => normalizeColumnKey(keyInput || label), [keyInput, label]);
  const normalizedPath = useMemo(
    () => (normalizedKey ? `columns/${normalizedKey}.py` : ""),
    [normalizedKey],
  );
  const keyConflict = useMemo(() => {
    if (!normalizedKey) {
      return false;
    }
    const comparable = normalizedKey.toLowerCase();
    return existingColumns.some((column) => column.key.toLowerCase() === comparable);
  }, [existingColumns, normalizedKey]);
  const pathConflict = useMemo(() => {
    if (!normalizedPath) {
      return false;
    }
    const comparable = normalizedPath.toLowerCase();
    return existingPaths.some((path) => path.toLowerCase() === comparable);
  }, [existingPaths, normalizedPath]);

  const helperMessage = useMemo(() => {
    if (!normalizedKey) {
      return "Enter a label or key to generate the file path.";
    }
    if (keyConflict) {
      return "A column with this key already exists.";
    }
    if (pathConflict) {
      return "A script already exists at this path.";
    }
    return "Columns are stored as Python scripts under columns/.";
  }, [keyConflict, normalizedKey, pathConflict]);

  const canSubmit = Boolean(
    normalizedKey &&
      label.trim().length > 0 &&
      !keyConflict &&
      !pathConflict &&
      normalizedPath,
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/20 backdrop-blur">
      <form
        className="w-[min(28rem,92vw)] space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
        onSubmit={async (event) => {
          event.preventDefault();
          const trimmedLabel = label.trim();
          if (!trimmedLabel) {
            setError("Column label is required.");
            return;
          }
          if (!normalizedKey) {
            setError("Column key is required.");
            return;
          }
          if (!normalizedPath) {
            setError("Unable to determine file path for the column.");
            return;
          }
          if (keyConflict) {
            setError("A column with this key already exists.");
            return;
          }
          if (pathConflict) {
            setError("A script already exists at this path.");
            return;
          }
          setIsSubmitting(true);
          setError(null);
          try {
            await onConfirm({ key: normalizedKey, label: trimmedLabel, required, path: normalizedPath });
            onClose();
          } catch (error) {
            setError(error instanceof Error ? error.message : "Failed to add column.");
          } finally {
            setIsSubmitting(false);
          }
        }}
      >
        <header className="space-y-1">
          <h2 className="text-base font-semibold text-slate-900">Add column</h2>
          <p className="text-xs text-slate-500">Create manifest metadata and scaffold a column script.</p>
        </header>

        <div className="space-y-3 text-sm">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Label
            <Input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="Postal Code"
              autoFocus
            />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Key
            <Input
              value={keyInput}
              onChange={(event) => {
                const value = event.target.value;
                setKeyInput(value);
                setKeyEdited(value.trim().length > 0);
              }}
              onBlur={(event) => {
                if (event.target.value.trim().length === 0) {
                  setKeyEdited(false);
                }
              }}
              placeholder="postal_code"
            />
          </label>
          <div className="space-y-1 text-[11px] text-slate-500">
            {normalizedPath ? (
              <p>
                Will create <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">{normalizedPath}</code>
              </p>
            ) : null}
            <p className={clsx(keyConflict || pathConflict ? "text-rose-600" : "text-slate-500")}>{helperMessage}</p>
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />
            Required
          </label>
        </div>

        {error ? <Alert tone="danger">{error}</Alert> : null}

        <footer className="flex justify-end gap-2 text-sm">
          <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={!canSubmit || isSubmitting}>
            {isSubmitting ? "Creating…" : "Create column"}
          </Button>
        </footer>
      </form>
    </div>
  );
}

interface ColumnSettingsInput {
  readonly label: string;
  readonly required: boolean;
  readonly enabled: boolean;
}

interface EditColumnDialogProps {
  readonly column: ManifestColumn;
  readonly onCancel: () => void;
  readonly onConfirm: (input: ColumnSettingsInput) => Promise<void>;
}

function EditColumnDialog({ column, onCancel, onConfirm }: EditColumnDialogProps) {
  const [label, setLabel] = useState(column.label);
  const [required, setRequired] = useState(Boolean(column.required));
  const [enabled, setEnabled] = useState(column.enabled !== false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  useEffect(() => {
    setLabel(column.label);
    setRequired(Boolean(column.required));
    setEnabled(column.enabled !== false);
  }, [column]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm">
      <form
        className="w-[min(28rem,92vw)] space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
        onSubmit={async (event) => {
          event.preventDefault();
          const trimmedLabel = label.trim();
          if (!trimmedLabel) {
            setError("Label is required.");
            return;
          }
          setIsSubmitting(true);
          setError(null);
          try {
            await onConfirm({ label: trimmedLabel, required, enabled });
          } catch (error) {
            setError(error instanceof Error ? error.message : "Failed to update column.");
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
          <p className="text-sm font-semibold text-slate-900">Edit column</p>
          <p className="text-xs text-slate-500">
            Update manifest metadata without touching the underlying script. File path stays {" "}
            <code className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-700">{column.path}</code>.
          </p>
        </header>

        <div className="space-y-3 text-sm">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Label
            <Input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Column label" />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span className="font-semibold uppercase tracking-wide text-slate-500">Required</span>
            <input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span className="font-semibold uppercase tracking-wide text-slate-500">Enabled</span>
            <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
          </label>
        </div>

        {error ? <Alert tone="danger">{error}</Alert> : null}

        <footer className="flex justify-end gap-2 text-sm">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save changes"}
          </Button>
        </footer>
      </form>
    </div>
  );
}

type VersionState = "active" | "inactive" | "archived";

function getVersionState(version: ConfigVersionRecord | null): VersionState | null {
  if (!version) {
    return null;
  }
  if (version.deleted_at) {
    return "archived";
  }
  if (version.status === "active" || Boolean(version.activated_at)) {
    return "active";
  }
  return "inactive";
}

function VersionStatusBadge({ state }: { readonly state: VersionState }) {
  const className = clsx(
    "rounded-full px-2 py-1 text-[11px] font-semibold uppercase tracking-wide",
    state === "active" && "bg-emerald-100 text-emerald-700",
    state === "inactive" && "bg-slate-100 text-slate-600",
    state === "archived" && "bg-rose-100 text-rose-700",
  );
  const label = state === "active" ? "Active" : state === "archived" ? "Archived" : "Inactive";
  return <span className={className}>{label}</span>;
}

type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

interface RunStatusSummary {
  readonly label: string;
  readonly tone: StatusTone;
}

interface RunStatusBadgeProps {
  readonly kind: "Validate" | "Test";
  readonly summary: RunStatusSummary;
  readonly completedLabel?: string | null;
  readonly title?: string | null;
}

const STATUS_TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "border-slate-200 bg-slate-100 text-slate-600",
  info: "border-sky-200 bg-sky-50 text-sky-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  danger: "border-rose-200 bg-rose-50 text-rose-700",
};

const STATUS_TONE_ICONS: Record<StatusTone, string> = {
  neutral: "○",
  info: "ⓘ",
  success: "✅",
  warning: "⚠️",
  danger: "❌",
};

function getValidationStatusSummary(state?: ValidationState | null): RunStatusSummary {
  if (!state) {
    return { label: "Not validated", tone: "neutral" };
  }
  switch (state.status) {
    case "running":
      return { label: "Validating…", tone: "info" };
    case "error":
      return { label: "Failed", tone: "danger" };
    case "stale":
      return { label: "Stale", tone: "warning" };
    case "success":
      if (state.ready) {
        return { label: "Validated", tone: "success" };
      }
      if (state.problems.length > 0) {
        return { label: "Needs fixes", tone: "warning" };
      }
      return { label: "Complete", tone: "info" };
    case "idle":
    default:
      return { label: "Not validated", tone: "neutral" };
  }
}

function getTestStatusSummary(state?: TestState | null, options?: { readonly ready?: boolean }): RunStatusSummary {
  if (!state) {
    return { label: "Not tested", tone: "neutral" };
  }
  switch (state.status) {
    case "running":
      return { label: "Testing…", tone: "info" };
    case "error":
      return { label: "Failed", tone: "danger" };
    case "stale":
      return { label: "Stale", tone: "warning" };
    case "success": {
      const ready = options?.ready ?? true;
      return ready ? { label: "Ready", tone: "success" } : { label: "Needs rerun", tone: "warning" };
    }
    case "idle":
    default:
      return { label: "Not tested", tone: "neutral" };
  }
}

function RunStatusBadge({ kind, summary, completedLabel, title }: RunStatusBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        STATUS_TONE_CLASSES[summary.tone],
      )}
      title={title ?? undefined}
    >
      <span className="text-[10px] uppercase tracking-wide">{kind}</span>
      <span className="font-semibold normal-case">{summary.label}</span>
      {completedLabel ? (
        <span className="text-[10px] font-normal normal-case opacity-80">• {completedLabel}</span>
      ) : null}
    </span>
  );
}
