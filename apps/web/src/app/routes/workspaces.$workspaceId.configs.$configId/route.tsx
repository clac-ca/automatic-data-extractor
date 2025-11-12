import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router";
import clsx from "clsx";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor, type CodeEditorHandle, type CodeEditorMarker } from "@ui/code-editor";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  composeManifestPatch,
  parseDocstringMetadata,
  parseManifest,
  useActivateConfigurationMutation,
  useConfigFileQuery,
  useConfigQuery,
  useDeactivateConfigurationMutation,
  useSaveConfigFileMutation,
  useValidateConfigurationMutation,
  type ConfigurationValidateResponse,
  type ManifestColumn,
  type ParsedManifest,
} from "@shared/configs";

const MANIFEST_PATH = "src/ade_config/manifest.json";
const ENABLE_MONACO = (import.meta.env.VITE_ENABLE_NEW_CONFIG_EDITOR ?? "").toLowerCase() === "true";

interface ColumnFormState {
  readonly id: string;
  readonly key: string;
  readonly label: string;
  readonly path: string;
  readonly required: boolean;
  readonly enabled: boolean;
  readonly depends_on: string[];
}

interface ScriptEditorState {
  readonly path: string;
  readonly content: string;
  readonly originalContent: string;
  readonly etag: string | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly isNew: boolean;
  readonly language: string;
  readonly size: number | null;
  readonly mtime: string | null;
}

interface LifecycleAlert {
  readonly type: "success" | "error";
  readonly message: string;
}

export default function WorkspaceConfigRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const manifestQuery = useConfigFileQuery({ workspaceId: workspace.id, configId, path: MANIFEST_PATH, enabled: Boolean(configId) });

  const saveManifestFile = useSaveConfigFileMutation(workspace.id, configId);
  const saveScriptFile = useSaveConfigFileMutation(workspace.id, configId);
  const validateConfig = useValidateConfigurationMutation(workspace.id, configId);
  const activateConfig = useActivateConfigurationMutation(workspace.id, configId);
  const deactivateConfig = useDeactivateConfigurationMutation(workspace.id, configId);

  const [parsedManifest, setParsedManifest] = useState<ParsedManifest | null>(null);
  const [columns, setColumns] = useState<ColumnFormState[]>([]);
  const [baselineColumns, setBaselineColumns] = useState<ColumnFormState[]>([]);
  const [selectedColumnId, setSelectedColumnId] = useState<string | null>(null);
  const [manifestMeta, setManifestMeta] = useState<{ etag: string | null } | null>(null);
  const [manifestMessage, setManifestMessage] = useState<string | null>(null);
  const [manifestErrorMessage, setManifestErrorMessage] = useState<string | null>(null);
  const [manifestParseError, setManifestParseError] = useState<string | null>(null);
  const [activePane, setActivePane] = useState<"columns" | "scripts">("columns");

  const [scriptState, setScriptState] = useState<ScriptEditorState | null>(null);
  const [scriptAlert, setScriptAlert] = useState<LifecycleAlert | null>(null);

  const [lifecycleAlert, setLifecycleAlert] = useState<LifecycleAlert | null>(null);

  const idCounter = useRef(0);

  const selectedColumn = useMemo(
    () => columns.find((column) => column.id === selectedColumnId) ?? null,
    [columns, selectedColumnId],
  );

  const manifestFile = manifestQuery.data;

  const columnFactory = useCallback((column: ManifestColumn): ColumnFormState => {
    idCounter.current += 1;
    return {
      id: `column-${idCounter.current}`,
      key: column.key ?? "",
      label: column.label ?? "",
      path: column.path ?? "",
      required: column.required ?? false,
      enabled: column.enabled ?? true,
      depends_on: Array.isArray(column.depends_on)
        ? column.depends_on.filter((value) => value != null && value.trim().length > 0)
        : [],
    };
  }, []);

  const manifestDirty = useMemo(() => {
    if (!parsedManifest) {
      return false;
    }
    return !columnsEqual(columns, baselineColumns);
  }, [columns, baselineColumns, parsedManifest]);

  useEffect(() => {
    if (manifestDirty) {
      setManifestMessage(null);
    }
  }, [manifestDirty]);

  useEffect(() => {
    if (!manifestFile) {
      return;
    }
    if (manifestFile.encoding !== "utf-8") {
      setManifestParseError("Manifest file must be UTF-8 encoded.");
      return;
    }
    if (manifestDirty) {
      return;
    }
    try {
      const payload = JSON.parse(manifestFile.content ?? "{}");
      const parsed = parseManifest(payload);
      idCounter.current = 0;
      const mapped = parsed.columns.map(columnFactory);
      setParsedManifest(parsed);
      setColumns(mapped.map(cloneColumn));
      setBaselineColumns(mapped.map(cloneColumn));
      setManifestMeta({ etag: manifestFile.etag ?? null });
      setManifestParseError(null);
      setManifestMessage(null);
      setManifestErrorMessage(null);
      setSelectedColumnId((current) => {
        if (current && mapped.some((column) => column.id === current)) {
          return current;
        }
        const first = mapped[0];
        return first ? first.id : null;
      });
    } catch (error) {
      console.error("Unable to parse manifest", error);
      setManifestParseError("Manifest JSON is invalid. Fix the file contents and try again.");
      setParsedManifest(null);
      setColumns([]);
      setBaselineColumns([]);
      setManifestMeta(null);
    }
  }, [manifestDirty, manifestFile, columnFactory]);

  const scriptPath = selectedColumn?.path?.trim() ?? "";

  const scriptFileQuery = useConfigFileQuery({
    workspaceId: workspace.id,
    configId,
    path: scriptPath.length > 0 ? scriptPath : null,
    enabled: Boolean(configId && scriptPath),
  });

  useEffect(() => {
    if (!scriptPath) {
      setScriptState(null);
      return;
    }
    const file = scriptFileQuery.data;
    const isFetching = scriptFileQuery.isFetching;
    const missingMessage = scriptFileQuery.isError
      ? scriptFileQuery.error instanceof Error
        ? scriptFileQuery.error.message
        : "Unable to load script file."
      : "Script file not found. Save to create it.";

    setScriptState((previous) => {
      if (!file) {
        if (isFetching) {
          if (previous && previous.path === scriptPath) {
            return { ...previous, loading: true };
          }
          return {
            path: scriptPath,
            content: previous && previous.path === scriptPath ? previous.content : "",
            originalContent: previous && previous.path === scriptPath ? previous.originalContent : "",
            etag: previous && previous.path === scriptPath ? previous.etag : null,
            loading: true,
            error: null,
            isNew: true,
            language: guessLanguage(scriptPath),
            size: null,
            mtime: null,
          } satisfies ScriptEditorState;
        }
        if (previous && previous.path === scriptPath) {
          if (previous.content !== previous.originalContent) {
            return { ...previous, loading: false, error: previous.error ?? null };
          }
          return {
            ...previous,
            loading: false,
            error: missingMessage,
            isNew: true,
          } satisfies ScriptEditorState;
        }
        return {
          path: scriptPath,
          content: "",
          originalContent: "",
          etag: null,
          loading: false,
          error: missingMessage,
          isNew: true,
          language: guessLanguage(scriptPath),
          size: null,
          mtime: null,
        } satisfies ScriptEditorState;
      }
      if (file.encoding !== "utf-8") {
        return {
          path: scriptPath,
          content: "",
          originalContent: "",
          etag: file.etag ?? null,
          loading: false,
          error: "Script file is not UTF-8 encoded.",
          isNew: false,
          language: guessLanguage(scriptPath),
          size: file.size ?? null,
          mtime: file.mtime ?? null,
        } satisfies ScriptEditorState;
      }
      if (previous && previous.path === scriptPath && previous.content !== previous.originalContent) {
        return previous;
      }
      return {
        path: scriptPath,
        content: file.content ?? "",
        originalContent: file.content ?? "",
        etag: file.etag ?? null,
        loading: false,
        error: null,
        isNew: false,
        language: guessLanguage(scriptPath),
        size: file.size ?? null,
        mtime: file.mtime ?? null,
      } satisfies ScriptEditorState;
    });
  }, [
    scriptPath,
    scriptFileQuery.data,
    scriptFileQuery.isFetching,
    scriptFileQuery.isError,
    scriptFileQuery.error,
  ]);

  const scriptDirty = Boolean(scriptState && scriptState.content !== scriptState.originalContent);

  useEffect(() => {
    if (scriptDirty) {
      setScriptAlert(null);
    }
  }, [scriptDirty]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!manifestDirty && !scriptDirty) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [manifestDirty, scriptDirty]);

  const scriptMarkers: CodeEditorMarker[] = useMemo(() => {
    if (!scriptState || !scriptState.path) {
      return [];
    }
    return (validateConfig.data?.issues ?? [])
      .filter((issue) => normalizePath(issue.path) === normalizePath(scriptState.path))
      .map((issue) => ({
        lineNumber: extractLineNumber(issue.message) ?? 1,
        message: issue.message,
        severity: "error" as const,
      }));
  }, [scriptState, validateConfig.data]);

  const docstringMetadata = useMemo(() => parseDocstringMetadata(scriptState?.content ?? ""), [scriptState?.content]);

  const lifecyclePending = activateConfig.isPending || deactivateConfig.isPending;

  const configRecord = configQuery.data;

  const handleColumnSelect = useCallback((columnId: string) => {
    setSelectedColumnId(columnId);
  }, []);

  const handleAddColumn = useCallback(() => {
    idCounter.current += 1;
    const newColumn: ColumnFormState = {
      id: `column-${idCounter.current}`,
      key: "",
      label: "",
      path: "",
      required: false,
      enabled: true,
      depends_on: [],
    };
    setColumns((prev) => [...prev, newColumn]);
    setSelectedColumnId(newColumn.id);
    setActivePane("columns");
  }, []);

  const handleRemoveColumn = useCallback((columnId: string) => {
    setColumns((previous) => {
      const index = previous.findIndex((column) => column.id === columnId);
      if (index === -1) {
        return previous;
      }
      const next = previous.filter((column) => column.id !== columnId);
      setSelectedColumnId((current) => {
        if (current !== columnId) {
          return current;
        }
        const fallback = next[index] ?? next[index - 1] ?? next[0] ?? null;
        return fallback ? fallback.id : null;
      });
      return next;
    });
  }, []);

  const handleMoveColumn = useCallback((columnId: string, direction: "up" | "down") => {
    setColumns((previous) => {
      const index = previous.findIndex((column) => column.id === columnId);
      if (index === -1) {
        return previous;
      }
      const nextIndex = direction === "up" ? index - 1 : index + 1;
      if (nextIndex < 0 || nextIndex >= previous.length) {
        return previous;
      }
      const copy = [...previous];
      const [item] = copy.splice(index, 1);
      copy.splice(nextIndex, 0, item);
      return copy;
    });
  }, []);

  const handleColumnChange = useCallback((columnId: string, patch: Partial<ColumnFormState>) => {
    setColumns((previous) =>
      previous.map((column) =>
        column.id === columnId
          ? {
              ...column,
              ...patch,
              depends_on: patch.depends_on ? [...patch.depends_on] : column.depends_on,
            }
          : column,
      ),
    );
  }, []);

  const handleSaveManifest = useCallback(async () => {
    if (!parsedManifest) {
      return;
    }
    setManifestMessage(null);
    setManifestErrorMessage(null);
    try {
      const manifestColumns = toManifestColumns(columns);
      const content = `${JSON.stringify(composeManifestPatch(parsedManifest, manifestColumns), null, 2)}\n`;
      const result = await saveManifestFile.mutateAsync({
        path: MANIFEST_PATH,
        content,
        etag: manifestMeta?.etag ?? undefined,
      });
      setManifestMeta({ etag: result?.etag ?? null });
      setBaselineColumns(columns.map(cloneColumn));
      setManifestMessage("Manifest saved.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to save manifest.";
      setManifestErrorMessage(message);
    }
  }, [columns, manifestMeta?.etag, parsedManifest, saveManifestFile]);

  const handleScriptChange = useCallback((value: string) => {
    setScriptState((previous) => (previous ? { ...previous, content: value } : previous));
  }, []);

  const handleSaveScript = useCallback(async () => {
    if (!scriptState) {
      return;
    }
    setScriptAlert(null);
    try {
      const result = await saveScriptFile.mutateAsync({
        path: scriptState.path,
        content: scriptState.content,
        etag: scriptState.etag ?? undefined,
        create: scriptState.isNew && !scriptState.etag ? true : undefined,
      });
      setScriptState((previous) => {
        if (!previous || previous.path !== scriptState.path) {
          return previous;
        }
        return {
          ...previous,
          originalContent: previous.content,
          etag: result?.etag ?? previous.etag ?? null,
          isNew: false,
          size: result?.size ?? previous.size,
          mtime: result?.mtime ?? previous.mtime,
          error: null,
        } satisfies ScriptEditorState;
      });
      setScriptAlert({ type: "success", message: "Script saved." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to save script.";
      setScriptAlert({ type: "error", message });
      setScriptState((previous) =>
        previous && previous.path === scriptState.path ? { ...previous, error: message } : previous,
      );
    }
  }, [saveScriptFile, scriptState]);

  const handleValidate = useCallback(async () => {
    setLifecycleAlert(null);
    try {
      await validateConfig.mutateAsync();
      setLifecycleAlert({ type: "success", message: "Validation completed." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Validation failed.";
      setLifecycleAlert({ type: "error", message });
    }
  }, [validateConfig]);

  const handleActivate = useCallback(async () => {
    setLifecycleAlert(null);
    try {
      await activateConfig.mutateAsync();
      await configQuery.refetch();
      setLifecycleAlert({ type: "success", message: "Configuration activated." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Activate failed.";
      setLifecycleAlert({ type: "error", message });
    }
  }, [activateConfig, configQuery]);

  const handleDeactivate = useCallback(async () => {
    setLifecycleAlert(null);
    try {
      await deactivateConfig.mutateAsync();
      await configQuery.refetch();
      setLifecycleAlert({ type: "success", message: "Configuration deactivated." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Deactivate failed.";
      setLifecycleAlert({ type: "error", message });
    }
  }, [configQuery, deactivateConfig]);

  if (!configId) {
    return <PageState title="Select a configuration" description="Choose a configuration to open the builder." />;
  }

  if (configQuery.isLoading || manifestQuery.isLoading) {
    return <PageState variant="loading" title="Loading configuration" description="Fetching configuration assets…" />;
  }

  if (configQuery.isError || !configRecord) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="This workspace does not include that configuration."
      />
    );
  }

  return (
    <div className="space-y-6">
      <ConfigHeader
        workspaceName={workspace.name}
        configName={configRecord.display_name}
        status={configRecord.status}
        updatedAt={configRecord.updated_at}
        onValidate={handleValidate}
        validating={validateConfig.isPending}
        onActivate={handleActivate}
        onDeactivate={handleDeactivate}
        lifecyclePending={lifecyclePending}
        canActivate={configRecord.status !== "active"}
        canDeactivate={configRecord.status === "active"}
      />

      {lifecycleAlert ? (
        <Alert tone={lifecycleAlert.type === "success" ? "success" : "danger"}>{lifecycleAlert.message}</Alert>
      ) : null}

      {configRecord.status !== "draft" ? (
        <Alert tone="warning" heading="Read-only configuration">
          This configuration is {configRecord.status}. Clone or switch to a draft to edit files.
        </Alert>
      ) : null}

      {manifestParseError ? <Alert tone="danger">{manifestParseError}</Alert> : null}
      {manifestQuery.isError ? (
        <Alert tone="danger">
          {manifestQuery.error instanceof Error
            ? manifestQuery.error.message
            : "Unable to load the manifest file."}
        </Alert>
      ) : null}

      <PaneToggle activePane={activePane} onChange={setActivePane} hasScript={Boolean(scriptPath)} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,420px),minmax(0,1fr)]">
        <div className={clsx(activePane === "columns" ? "block" : "hidden", "xl:block")}>
        <ColumnsPanel
          columns={columns}
          selectedColumnId={selectedColumnId}
          onSelect={handleColumnSelect}
          onAdd={handleAddColumn}
          onRemove={handleRemoveColumn}
          onMove={handleMoveColumn}
          onChange={handleColumnChange}
          onSave={handleSaveManifest}
          manifestDirty={manifestDirty}
          saving={saveManifestFile.isPending}
          message={manifestMessage}
          error={manifestErrorMessage}
          disabled={configRecord.status !== "draft"}
          onOpenScript={() => setActivePane("scripts")}
          manifest={parsedManifest}
        />
        </div>

        <div className={clsx(activePane === "scripts" ? "block" : "hidden", "xl:block")}>
          <ScriptPanel
            column={selectedColumn}
            script={scriptState}
            onChange={handleScriptChange}
            onSave={handleSaveScript}
            saving={saveScriptFile.isPending}
            dirty={scriptDirty}
            alert={scriptAlert}
            validation={validateConfig.data ?? null}
            docstring={docstringMetadata}
            markers={ENABLE_MONACO ? scriptMarkers : []}
            enableMonaco={ENABLE_MONACO}
            disabled={configRecord.status !== "draft"}
            onShowColumns={() => setActivePane("columns")}
          />
        </div>
      </div>
    </div>
  );
}

function ConfigHeader({
  workspaceName,
  configName,
  status,
  updatedAt,
  onValidate,
  validating,
  onActivate,
  onDeactivate,
  lifecyclePending,
  canActivate,
  canDeactivate,
}: {
  readonly workspaceName: string;
  readonly configName: string;
  readonly status: string;
  readonly updatedAt: string;
  readonly onValidate: () => void;
  readonly validating: boolean;
  readonly onActivate: () => void;
  readonly onDeactivate: () => void;
  readonly lifecyclePending: boolean;
  readonly canActivate: boolean;
  readonly canDeactivate: boolean;
}) {
  return (
    <header className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{workspaceName}</p>
        <h1 className="text-xl font-semibold text-slate-900">{configName}</h1>
        <p className="text-sm text-slate-600">
          <span className="font-medium">Status:</span> {status}
          <span className="mx-2 text-slate-400">•</span>
          <span className="font-medium">Updated:</span> {formatDateTime(updatedAt)}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onValidate} isLoading={validating}>
          Run validation
        </Button>
        <Button variant="secondary" onClick={onActivate} disabled={!canActivate} isLoading={lifecyclePending}>
          Activate
        </Button>
        <Button variant="ghost" onClick={onDeactivate} disabled={!canDeactivate} isLoading={lifecyclePending}>
          Deactivate
        </Button>
      </div>
    </header>
  );
}

function PaneToggle({
  activePane,
  onChange,
  hasScript,
}: {
  readonly activePane: "columns" | "scripts";
  readonly onChange: (pane: "columns" | "scripts") => void;
  readonly hasScript: boolean;
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-1 text-sm shadow-sm xl:hidden">
      <button
        type="button"
        className={clsx(
          "flex-1 rounded-md px-3 py-2 font-semibold transition",
          activePane === "columns" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100",
        )}
        onClick={() => onChange("columns")}
      >
        Columns
      </button>
      <button
        type="button"
        className={clsx(
          "flex-1 rounded-md px-3 py-2 font-semibold transition",
          activePane === "scripts" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100",
          !hasScript ? "opacity-75" : null,
        )}
        onClick={() => onChange("scripts")}
      >
        Scripts
      </button>
    </div>
  );
}

function ColumnsPanel({
  columns,
  selectedColumnId,
  onSelect,
  onAdd,
  onRemove,
  onMove,
  onChange,
  onSave,
  manifestDirty,
  saving,
  message,
  error,
  disabled,
  onOpenScript,
  manifest,
}: {
  readonly columns: readonly ColumnFormState[];
  readonly selectedColumnId: string | null;
  readonly onSelect: (id: string) => void;
  readonly onAdd: () => void;
  readonly onRemove: (id: string) => void;
  readonly onMove: (id: string, direction: "up" | "down") => void;
  readonly onChange: (id: string, patch: Partial<ColumnFormState>) => void;
  readonly onSave: () => void;
  readonly manifestDirty: boolean;
  readonly saving: boolean;
  readonly message: string | null;
  readonly error: string | null;
  readonly disabled: boolean;
  readonly onOpenScript: () => void;
  readonly manifest: ParsedManifest | null;
}) {
  const selectedColumn = columns.find((column) => column.id === selectedColumnId) ?? null;
  const dependsOnValue = selectedColumn?.depends_on.join(", ") ?? "";

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Columns</h2>
            <p className="text-xs text-slate-500">Manage manifest columns and their associated scripts.</p>
          </div>
          <Button size="sm" onClick={onAdd} disabled={disabled}>
            Add column
          </Button>
        </div>
        {manifest ? <ManifestSummary manifest={manifest} /> : null}
        <ul className="max-h-80 divide-y divide-slate-200 overflow-y-auto">
          {columns.length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-slate-500">No columns defined.</li>
          ) : (
            columns.map((column, index) => {
              const isActive = column.id === selectedColumnId;
              const displayLabel = column.label || column.key || `Column ${index + 1}`;
              return (
                <li key={column.id} className="flex items-center justify-between px-4 py-3">
                  <button
                    type="button"
                    onClick={() => onSelect(column.id)}
                    className={clsx(
                      "flex min-w-0 flex-1 flex-col text-left",
                      isActive ? "text-brand-600" : "text-slate-700",
                    )}
                  >
                    <span className="truncate text-sm font-medium">{displayLabel}</span>
                    <span className="truncate text-xs text-slate-500">{column.path || "No script path"}</span>
                  </button>
                  <div className="ml-3 flex items-center gap-1">
                    <IconButton
                      label="Move up"
                      onClick={() => onMove(column.id, "up")}
                      disabled={index === 0 || disabled}
                      icon="▲"
                    />
                    <IconButton
                      label="Move down"
                      onClick={() => onMove(column.id, "down")}
                      disabled={index === columns.length - 1 || disabled}
                      icon="▼"
                    />
                    <IconButton label="Remove" onClick={() => onRemove(column.id)} disabled={disabled} icon="✕" />
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </section>

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Column details</h3>
          <Button
            size="sm"
            variant="secondary"
            onClick={onSave}
            disabled={!manifestDirty || disabled}
            isLoading={saving}
          >
            Save manifest
          </Button>
        </div>
        {message ? <Alert tone="success">{message}</Alert> : null}
        {error ? <Alert tone="danger">{error}</Alert> : null}

        {selectedColumn ? (
          <div className="space-y-4">
            <FormField label="Column key" required>
              <Input
                value={selectedColumn.key}
                onChange={(event) => onChange(selectedColumn.id, { key: event.target.value })}
                placeholder="billing_cycle"
                disabled={disabled}
              />
            </FormField>
            <FormField label="Display label" hint="Shown in UI summaries and documentation.">
              <Input
                value={selectedColumn.label}
                onChange={(event) => onChange(selectedColumn.id, { label: event.target.value })}
                placeholder="Billing cycle"
                disabled={disabled}
              />
            </FormField>
            <FormField label="Script path" hint="Relative to the configuration package root.">
              <Input
                value={selectedColumn.path}
                onChange={(event) => onChange(selectedColumn.id, { path: event.target.value })}
                placeholder="src/ade_config/column_detectors/billing_cycle.py"
                disabled={disabled}
              />
            </FormField>
            <FormField label="Dependencies" hint="Comma-separated list of other column keys.">
              <Input
                value={dependsOnValue}
                onChange={(event) =>
                  onChange(selectedColumn.id, {
                    depends_on: event.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter((value) => value.length > 0),
                  })
                }
                placeholder="member_id, enrollment_id"
                disabled={disabled}
              />
            </FormField>
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                  checked={selectedColumn.required}
                  onChange={(event) => onChange(selectedColumn.id, { required: event.target.checked })}
                  disabled={disabled}
                />
                <span className="text-slate-700">Required field</span>
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                  checked={selectedColumn.enabled}
                  onChange={(event) => onChange(selectedColumn.id, { enabled: event.target.checked })}
                  disabled={disabled}
                />
                <span className="text-slate-700">Enabled</span>
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onOpenScript()}
                disabled={!selectedColumn.path}
              >
                Manage script
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-600">Select a column to edit its manifest details.</p>
        )}
      </section>
    </div>
  );
}

function ScriptPanel({
  column,
  script,
  onChange,
  onSave,
  saving,
  dirty,
  alert,
  validation,
  docstring,
  markers,
  enableMonaco,
  disabled,
  onShowColumns,
}: {
  readonly column: ColumnFormState | null;
  readonly script: ScriptEditorState | null;
  readonly onChange: (value: string) => void;
  readonly onSave: () => void;
  readonly saving: boolean;
  readonly dirty: boolean;
  readonly alert: LifecycleAlert | null;
  readonly validation: ConfigurationValidateResponse | null;
  readonly docstring: ReturnType<typeof parseDocstringMetadata>;
  readonly markers: readonly CodeEditorMarker[];
  readonly enableMonaco: boolean;
  readonly disabled: boolean;
  readonly onShowColumns: () => void;
}) {
  const editorRef = useRef<CodeEditorHandle | null>(null);
  const handleFocusIssue = useCallback(
    (lineNumber: number | null) => {
      if (!enableMonaco || lineNumber == null) {
        return;
      }
      editorRef.current?.revealLine(lineNumber);
    },
    [enableMonaco],
  );

  if (!column) {
    return (
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
        <p>Select a column to view or edit its script.</p>
        <Button size="sm" variant="secondary" onClick={onShowColumns}>
          Choose a column
        </Button>
      </section>
    );
  }

  const scriptPath = column.path?.trim();

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-slate-200 pb-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{column.label || column.key || "Unnamed column"}</h2>
          <p className="text-xs text-slate-500">{scriptPath || "No script linked."}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={onSave} disabled={!dirty || disabled} isLoading={saving}>
            Save script
          </Button>
          <Button size="sm" variant="ghost" onClick={onShowColumns}>
            Back to columns
          </Button>
        </div>
      </div>

      {alert ? (
        <Alert tone={alert.type === "success" ? "success" : "danger"}>{alert.message}</Alert>
      ) : null}

      {script ? (
        <div className="space-y-4">
          {script.error ? <Alert tone="danger">{script.error}</Alert> : null}
          {enableMonaco ? (
            <div className="h-[400px] overflow-hidden rounded-lg border border-slate-200">
              <CodeEditor
                ref={editorRef}
                value={script.content}
                onChange={onChange}
                language={script.language}
                readOnly={disabled}
                onSaveShortcut={onSave}
                markers={markers}
              />
            </div>
          ) : (
            <textarea
              value={script.content}
              onChange={(event) => onChange(event.target.value)}
              className="h-[400px] w-full rounded-lg border border-slate-200 bg-slate-950 p-4 font-mono text-sm text-slate-50"
              spellCheck={false}
              readOnly={disabled}
            />
          )}

          <DocstringPreview metadata={docstring} />

          <ValidationResults
            validation={validation}
            scriptPath={script.path}
            onFocusIssue={enableMonaco ? handleFocusIssue : undefined}
          />

          <ScriptMeta script={script} dirty={dirty} />
        </div>
      ) : (
        <p className="text-sm text-slate-600">
          {scriptPath
            ? "Loading script contents…"
            : "Add a script path to this column to enable code editing."}
        </p>
      )}
    </section>
  );
}

function DocstringPreview({ metadata }: { readonly metadata: ReturnType<typeof parseDocstringMetadata> }) {
  const { name, description, version, summary } = metadata;

  if (!name && !description && !version && !summary) {
    return (
      <div className="space-y-3">
        <Alert tone="info">
          Include a docstring at the top of the script with Name, Description, and Version fields to help reviewers understand
          its purpose.
        </Alert>
        <DocstringChecklist metadata={metadata} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Docstring preview</h3>
        <dl className="mt-3 space-y-2">
          {name ? (
            <div>
              <dt className="text-xs font-medium text-slate-500">Name</dt>
              <dd className="text-sm text-slate-800">{name}</dd>
            </div>
          ) : null}
          {summary ? (
            <div>
              <dt className="text-xs font-medium text-slate-500">Summary</dt>
              <dd className="text-sm text-slate-800">{summary}</dd>
            </div>
          ) : null}
          {description ? (
            <div>
              <dt className="text-xs font-medium text-slate-500">Description</dt>
              <dd className="text-sm text-slate-800">{description}</dd>
            </div>
          ) : null}
          {version ? (
            <div>
              <dt className="text-xs font-medium text-slate-500">Version</dt>
              <dd className="text-sm text-slate-800">{version}</dd>
            </div>
          ) : null}
        </dl>
      </div>
      <DocstringChecklist metadata={metadata} />
    </div>
  );
}

function ValidationResults({
  validation,
  scriptPath,
  onFocusIssue,
}: {
  readonly validation: ConfigurationValidateResponse | null;
  readonly scriptPath: string;
  readonly onFocusIssue?: (lineNumber: number | null) => void;
}) {
  if (!validation) {
    return null;
  }

  if (!validation.issues || validation.issues.length === 0) {
    return <Alert tone="success">Validation passed without issues.</Alert>;
  }

  const normalizedPath = normalizePath(scriptPath);
  const normalizedIssues = validation.issues.map((issue) => ({
    ...issue,
    lineNumber: extractLineNumber(issue.message),
    isScriptIssue: normalizePath(issue.path) === normalizedPath,
  }));

  const scriptIssues = normalizedIssues.filter((issue) => issue.isScriptIssue);
  const otherIssues = normalizedIssues.filter((issue) => !issue.isScriptIssue);
  const mapIssue = (issue: typeof normalizedIssues[number]): IssueWithMetadata => ({
    path: issue.path,
    message: issue.message,
    lineNumber: issue.lineNumber ?? null,
  });
  const focusable = typeof onFocusIssue === "function";

  return (
    <div className="space-y-3">
      <Alert tone="warning" heading="Validation issues detected">
        Review the issues below and update the script before activating this configuration.
      </Alert>
      <IssueList
        title={scriptIssues.length > 0 ? "Issues for this script" : "Configuration issues"}
        issues={(scriptIssues.length > 0 ? scriptIssues : normalizedIssues).map(mapIssue)}
        onFocusIssue={focusable ? onFocusIssue : undefined}
      />
      {scriptIssues.length > 0 && otherIssues.length > 0 ? (
        <IssueList title="Other configuration issues" issues={otherIssues.map(mapIssue)} />
      ) : null}
    </div>
  );
}

function ScriptMeta({ script, dirty }: { readonly script: ScriptEditorState | null; readonly dirty: boolean }) {
  if (!script) {
    return null;
  }

  return (
    <dl className="grid grid-cols-1 gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 md:grid-cols-2">
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">File size</dt>
        <dd>{script.size != null ? formatFileSize(script.size) : "Unknown"}</dd>
      </div>
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Last modified</dt>
        <dd>{script.mtime ? formatDateTime(script.mtime) : "Unknown"}</dd>
      </div>
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Language</dt>
        <dd className="font-mono text-xs uppercase text-slate-600">{script.language || "plain"}</dd>
      </div>
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Status</dt>
        <dd className={clsx("font-medium", dirty ? "text-warning-700" : script.isNew ? "text-brand-700" : "text-emerald-700")}> 
          {dirty ? "Unsaved changes" : script.isNew ? "New file" : "Saved"}
        </dd>
      </div>
      <div className="md:col-span-2">
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">ETag</dt>
        <dd className="font-mono text-xs text-slate-500">{script.etag ?? "Not available"}</dd>
      </div>
    </dl>
  );
}

function ManifestSummary({ manifest }: { readonly manifest: ParsedManifest }) {
  return (
    <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
      <dl className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Manifest name</dt>
          <dd className="font-medium text-slate-900">{manifest.name}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Columns</dt>
          <dd className="font-medium text-slate-900">{manifest.columns.length}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Files digest</dt>
          <dd className="font-mono text-xs text-slate-500">{manifest.filesHash}</dd>
        </div>
      </dl>
    </div>
  );
}

function DocstringChecklist({ metadata }: { readonly metadata: ReturnType<typeof parseDocstringMetadata> }) {
  const fields = [
    {
      key: "name",
      label: "Name",
      present: Boolean(metadata.name),
      description: "Shown in summaries and approvals.",
    },
    {
      key: "description",
      label: "Description",
      present: Boolean(metadata.description),
      description: "Explains what the script does.",
    },
    {
      key: "version",
      label: "Version",
      present: Boolean(metadata.version),
      description: "Track revisions for releases.",
    },
    {
      key: "summary",
      label: "Summary",
      present: Boolean(metadata.summary),
      description: "Used as a quick-glance tooltip.",
    },
  ];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Docstring checklist</h3>
      <ul className="mt-3 space-y-2">
        {fields.map((field) => (
          <li
            key={field.key}
            className="flex items-start justify-between gap-3 rounded-md border border-slate-200/70 bg-slate-50 px-3 py-2"
          >
            <div>
              <p className="text-sm font-medium text-slate-800">{field.label}</p>
              <p className="text-xs text-slate-500">{field.description}</p>
            </div>
            <span
              className={clsx(
                "text-xs font-semibold uppercase",
                field.present ? "text-emerald-600" : "text-warning-600",
              )}
            >
              {field.present ? "Ready" : "Missing"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface IssueWithMetadata {
  readonly path: string;
  readonly message: string;
  readonly lineNumber: number | null;
}

function IssueList({
  title,
  issues,
  onFocusIssue,
}: {
  readonly title: string;
  readonly issues: readonly IssueWithMetadata[];
  readonly onFocusIssue?: (lineNumber: number | null) => void;
}) {
  if (issues.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      <ul className="space-y-2 text-sm text-slate-700">
        {issues.map((issue, index) => (
          <li key={`${issue.path}-${index}`} className="space-y-2 rounded-lg border border-warning-200 bg-warning-50 p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold text-warning-700">{issue.path}</p>
              {issue.lineNumber != null ? (
                <span className="text-xs font-medium uppercase text-warning-600">Line {issue.lineNumber}</span>
              ) : null}
            </div>
            <p className="text-warning-700">{issue.message}</p>
            {onFocusIssue && issue.lineNumber != null ? (
              <button
                type="button"
                onClick={() => onFocusIssue(issue.lineNumber)}
                className="text-xs font-semibold text-brand-700 underline-offset-2 hover:underline"
              >
                Jump to line {issue.lineNumber}
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  icon,
}: {
  readonly label: string;
  readonly onClick: () => void;
  readonly disabled?: boolean;
  readonly icon: string;
}) {
  return (
    <button
      type="button"
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-xs text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
    >
      {icon}
    </button>
  );
}

function guessLanguage(path: string): string {
  const normalized = path.toLowerCase();
  if (normalized.endsWith(".py")) {
    return "python";
  }
  if (normalized.endsWith(".ts")) {
    return "typescript";
  }
  if (normalized.endsWith(".js")) {
    return "javascript";
  }
  if (normalized.endsWith(".json")) {
    return "json";
  }
  return "plaintext";
}

function cloneColumn(column: ColumnFormState): ColumnFormState {
  return {
    ...column,
    depends_on: [...column.depends_on],
  };
}

function columnsEqual(a: readonly ColumnFormState[], b: readonly ColumnFormState[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  for (let index = 0; index < a.length; index += 1) {
    const first = a[index];
    const second = b[index];
    if (!first || !second) {
      return false;
    }
    if (
      first.key.trim() !== second.key.trim() ||
      first.label.trim() !== second.label.trim() ||
      first.path.trim() !== second.path.trim() ||
      first.required !== second.required ||
      first.enabled !== second.enabled
    ) {
      return false;
    }
    const firstDepends = first.depends_on.map((value) => value.trim()).filter((value) => value.length > 0);
    const secondDepends = second.depends_on.map((value) => value.trim()).filter((value) => value.length > 0);
    if (firstDepends.length !== secondDepends.length) {
      return false;
    }
    for (let depIndex = 0; depIndex < firstDepends.length; depIndex += 1) {
      if (firstDepends[depIndex] !== secondDepends[depIndex]) {
        return false;
      }
    }
  }
  return true;
}

function toManifestColumns(columns: readonly ColumnFormState[]): ManifestColumn[] {
  return columns.map((column, index) => ({
    key: column.key.trim(),
    label: column.label.trim() || column.key.trim(),
    path: column.path.trim(),
    ordinal: index,
    required: column.required,
    enabled: column.enabled,
    depends_on: column.depends_on
      .map((value) => value.trim())
      .filter((value, position, array) => value.length > 0 && array.indexOf(value) === position),
  }));
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch (error) {
    return value;
  }
}

function formatFileSize(size: number): string {
  if (!Number.isFinite(size) || size < 0) {
    return "Unknown";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function extractLineNumber(message: string): number | null {
  const match = /line\s+(\d+)/i.exec(message);
  if (match) {
    const parsed = Number.parseInt(match[1] ?? "", 10);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return null;
}

function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").trim();
}
