import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import clsx from "clsx";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";
import { Input } from "@ui/input";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  useActivateConfigurationMutation,
  useConfigFileQuery,
  useConfigFilesQuery,
  useConfigQuery,
  useDeactivateConfigurationMutation,
  useRenameConfigFileMutation,
  useValidateConfigurationMutation,
  type ConfigurationValidateResponse,
  type FileEntry,
  type FileReadJson,
} from "@shared/configs";
import { useConfigEditorState } from "./useConfigEditorState";
import type { EditorTab } from "./useConfigEditorState";

interface TreeNode {
  readonly entry: FileEntry;
  readonly children: TreeNode[];
}

interface FlattenedNode {
  readonly entry: FileEntry;
  readonly depth: number;
}

interface ManifestColumnSummary {
  readonly key: string;
  readonly label: string;
  readonly path: string;
  readonly required: boolean;
  readonly enabled: boolean;
}

interface ManifestSummary {
  readonly name: string;
  readonly columns: readonly ManifestColumnSummary[];
  readonly transformPath: string | null;
  readonly validatorsPath: string | null;
}

interface ManifestParseResult {
  readonly summary: ManifestSummary | null;
  readonly error: string | null;
}

const MANIFEST_PATH = "src/ade_config/manifest.json";

export default function WorkspaceConfigRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const filesQuery = useConfigFilesQuery({ workspaceId: workspace.id, configId, depth: "infinity", enabled: Boolean(configId) });
  const manifestQuery = useConfigFileQuery({ workspaceId: workspace.id, configId, path: MANIFEST_PATH, enabled: Boolean(configId) });

  const editor = useConfigEditorState({
    workspaceId: workspace.id,
    configId,
    onSaved: () => {
      void filesQuery.refetch();
      void manifestQuery.refetch();
    },
  });

  const validateConfig = useValidateConfigurationMutation(workspace.id, configId);
  const activateConfig = useActivateConfigurationMutation(workspace.id, configId);
  const deactivateConfig = useDeactivateConfigurationMutation(workspace.id, configId);
  const renameFile = useRenameConfigFileMutation(workspace.id, configId);

  const [fileFilter, setFileFilter] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(["", "src/ade_config/", "assets/"]));
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [lifecycleMessage, setLifecycleMessage] = useState<string | null>(null);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);

  const configData = configQuery.data;
  const listing = filesQuery.data;

  useEffect(() => {
    if (!listing) {
      return;
    }
    setExpanded((prev) => {
      if (prev.size > 1) {
        return prev;
      }
      const next = new Set(prev);
      listing.entries
        .filter((entry) => entry.kind === "dir" && entry.depth <= 1)
        .forEach((entry) => next.add(entry.path));
      return next;
    });
  }, [listing]);

  const tree = useMemo(() => buildFileTree(listing?.entries ?? []), [listing?.entries]);
  const visibleSet = useMemo(() => deriveVisibleSet(listing?.entries ?? [], fileFilter), [listing?.entries, fileFilter]);
  const treeItems = useMemo(() => flattenTree(tree, expanded, visibleSet), [tree, expanded, visibleSet]);

  const editable = configData?.status === "draft";
  const activeTab = editor.activeTab;
  const dirty = Boolean(activeTab && activeTab.encoding === "utf-8" && activeTab.content !== activeTab.originalContent);

  const manifestDetails = useMemo(() => parseManifestFile(manifestQuery.data), [manifestQuery.data]);
  const manifestError = manifestDetails.error ?? (manifestQuery.isError ? (manifestQuery.error as Error).message : null);

  const handleToggleNode = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleRenameSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!renameTarget) {
      return;
    }
    setRenameError(null);
    renameFile.mutate(
      { fromPath: renameTarget, toPath: renameValue, overwrite: false },
      {
        onSuccess: (result) => {
          editor.renameTabPath(renameTarget, result.to);
          setRenameTarget(null);
          filesQuery.refetch();
        },
        onError: (error) => {
          setRenameError(error instanceof Error ? error.message : "Unable to rename file.");
        },
      },
    );
  };

  const handleValidate = async () => {
    setLifecycleMessage(null);
    setLifecycleError(null);
    try {
      await validateConfig.mutateAsync();
      setLifecycleMessage("Validation completed.");
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : "Validation failed.");
    }
  };

  const handleActivate = async () => {
    setLifecycleMessage(null);
    setLifecycleError(null);
    try {
      await activateConfig.mutateAsync();
      await configQuery.refetch();
      setLifecycleMessage("Configuration activated.");
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : "Activate failed.");
    }
  };

  const handleDeactivate = async () => {
    setLifecycleMessage(null);
    setLifecycleError(null);
    try {
      await deactivateConfig.mutateAsync();
      await configQuery.refetch();
      setLifecycleMessage("Configuration deactivated.");
    } catch (error) {
      setLifecycleError(error instanceof Error ? error.message : "Deactivate failed.");
    }
  };

  const lifecyclePending = activateConfig.isPending || deactivateConfig.isPending;

  if (!configId) {
    return <PageState title="Select a configuration" description="Choose a configuration to open the builder." />;
  }

  if (configQuery.isLoading || filesQuery.isLoading) {
    return <PageState variant="loading" title="Loading configuration" description="Fetching file tree…" />;
  }

  if (configQuery.isError || !configData) {
    return (
      <PageState variant="error" title="Configuration not found" description="This workspace does not include that configuration." />
    );
  }

  if (filesQuery.isError || !listing) {
    return <PageState variant="error" title="Unable to load files" description="Ensure the configuration exists on disk and try again." />;
  }

  return (
    <div className="space-y-4">
      <ConfigIDEHeader
        configName={configData.display_name}
        workspaceName={workspace.name}
        status={configData.status}
        updatedAt={configData.updated_at}
        onValidate={handleValidate}
        validating={validateConfig.isPending}
        onActivate={handleActivate}
        onDeactivate={handleDeactivate}
        lifecyclePending={lifecyclePending}
        canActivate={configData.status !== "active"}
        canDeactivate={configData.status === "active"}
      />

      {lifecycleMessage ? <Alert tone="success">{lifecycleMessage}</Alert> : null}
      {lifecycleError ? <Alert tone="danger">{lifecycleError}</Alert> : null}

      {!editable ? (
        <Alert tone="warning" heading="Read-only configuration">
          This configuration is {configData.status}. Clone or switch to a draft to edit files.
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[260px,minmax(0,1fr),320px]">
        <FileSidebar
          filter={fileFilter}
          onFilterChange={setFileFilter}
          summary={listing.summary}
          generatedAt={listing.generated_at}
          onRefresh={() => void filesQuery.refetch()}
          isRefreshing={filesQuery.isFetching}
          items={treeItems}
          expanded={expanded}
          onToggle={handleToggleNode}
          onSelect={(path) => editor.openTab(path)}
          activePath={editor.activePath}
        />

        <EditorWorkspace
          tabs={editor.tabs}
          activeTab={activeTab}
          activePath={editor.activePath}
          onSelectTab={editor.setActivePath}
          onCloseTab={editor.closeTab}
          updateContent={editor.updateContent}
          isSaving={editor.isSaving}
          dirty={dirty}
          editable={editable}
          onSave={editor.saveActiveTab}
          onRename={() => {
            if (editor.activePath) {
              setRenameTarget(editor.activePath);
              setRenameValue(editor.activePath);
            }
          }}
        />

        <InspectorPanel
          manifest={{ summary: manifestDetails.summary, error: manifestError, isLoading: manifestQuery.isLoading }}
          manifestPath={MANIFEST_PATH}
          onOpenManifest={() => editor.openTab(MANIFEST_PATH)}
          onOpenFile={(path) => {
            if (path) {
              editor.openTab(path);
            }
          }}
          validation={validateConfig.data ?? null}
          validationError={validateConfig.isError ? (validateConfig.error as Error).message : null}
          isValidationRunning={validateConfig.isPending}
          onValidate={handleValidate}
        />
      </div>

      {renameTarget ? (
        <RenameDialog
          path={renameTarget}
          value={renameValue}
          onChange={setRenameValue}
          onClose={() => {
            setRenameTarget(null);
            setRenameError(null);
          }}
          onSubmit={handleRenameSubmit}
          isSubmitting={renameFile.isPending}
          error={renameError}
        />
      ) : null}
    </div>
  );
}

function ConfigIDEHeader({
  configName,
  workspaceName,
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
  readonly configName: string;
  readonly workspaceName: string;
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
    <header className="rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-slate-500">Workspace · {workspaceName}</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">{configName}</h1>
            <StatusBadge status={status} />
          </div>
          <p className="text-sm text-slate-500">Updated {formatTimestamp(updatedAt)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onValidate} isLoading={validating}>
            Validate
          </Button>
          {canActivate ? (
            <Button variant="primary" size="sm" onClick={onActivate} isLoading={lifecyclePending}>
              Activate
            </Button>
          ) : null}
          {canDeactivate ? (
            <Button variant="ghost" size="sm" onClick={onDeactivate} isLoading={lifecyclePending}>
              Deactivate
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function StatusBadge({ status }: { readonly status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "active"
      ? "bg-emerald-100 text-emerald-700"
      : normalized === "draft"
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-200 text-slate-700";
  return (
    <span className={clsx("rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide", tone)}>{status}</span>
  );
}

function FileSidebar({
  filter,
  onFilterChange,
  summary,
  generatedAt,
  onRefresh,
  isRefreshing,
  items,
  expanded,
  onToggle,
  onSelect,
  activePath,
}: {
  readonly filter: string;
  readonly onFilterChange: (value: string) => void;
  readonly summary: { files: number; directories: number };
  readonly generatedAt: string;
  readonly onRefresh: () => void;
  readonly isRefreshing: boolean;
  readonly items: readonly FlattenedNode[];
  readonly expanded: ReadonlySet<string>;
  readonly onToggle: (path: string) => void;
  readonly onSelect: (path: string) => void;
  readonly activePath: string | null;
}) {
  return (
    <aside className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Files</p>
          <Button variant="ghost" size="sm" onClick={onRefresh} isLoading={isRefreshing}>
            Refresh
          </Button>
        </div>
        <Input
          value={filter}
          onChange={(event) => onFilterChange(event.target.value)}
          placeholder="Filter files"
          className="mt-3"
        />
        <p className="mt-2 text-xs text-slate-500">
          {summary.files} files · {summary.directories} directories
        </p>
        <p className="text-[11px] text-slate-400">Generated {formatTimestamp(generatedAt)}</p>
      </div>
      <FileTree items={items} expanded={expanded} onToggle={onToggle} onSelect={onSelect} activePath={activePath} />
    </aside>
  );
}

function InspectorPanel({
  manifest,
  manifestPath,
  onOpenManifest,
  onOpenFile,
  validation,
  validationError,
  isValidationRunning,
  onValidate,
}: {
  readonly manifest: { summary: ManifestSummary | null; error: string | null; isLoading: boolean };
  readonly manifestPath: string;
  readonly onOpenManifest: () => void;
  readonly onOpenFile: (path: string | null | undefined) => void;
  readonly validation: ConfigurationValidateResponse | null;
  readonly validationError: string | null;
  readonly isValidationRunning: boolean;
  readonly onValidate: () => void;
}) {
  return (
    <aside className="flex h-full flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <ManifestPanel manifest={manifest} manifestPath={manifestPath} onOpenManifest={onOpenManifest} onOpenFile={onOpenFile} />
      <ValidationPanel
        validation={validation}
        validationError={validationError}
        isValidationRunning={isValidationRunning}
        onValidate={onValidate}
      />
    </aside>
  );
}

function ManifestPanel({
  manifest,
  manifestPath,
  onOpenManifest,
  onOpenFile,
}: {
  readonly manifest: { summary: ManifestSummary | null; error: string | null; isLoading: boolean };
  readonly manifestPath: string;
  readonly onOpenManifest: () => void;
  readonly onOpenFile: (path: string | null | undefined) => void;
}) {
  return (
    <section>
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Manifest</p>
          <p className="text-sm font-semibold text-slate-900">{manifest.summary?.name ?? "Configuration manifest"}</p>
        </div>
        <Button size="sm" variant="secondary" onClick={onOpenManifest}>
          Open file
        </Button>
      </header>
      {manifest.isLoading ? (
        <p className="text-sm text-slate-500">Loading manifest…</p>
      ) : manifest.error ? (
        <Alert tone="danger">{manifest.error}</Alert>
      ) : manifest.summary ? (
        <div className="space-y-3 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Columns</p>
            {manifest.summary.columns.length === 0 ? (
              <p className="text-sm text-slate-500">No columns defined.</p>
            ) : (
              <ul className="mt-2 max-h-48 space-y-1 overflow-auto">
                {manifest.summary.columns.map((column) => (
                  <li key={column.key} className="rounded-xl border border-slate-100 px-2 py-2 text-xs">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-slate-900">{column.label}</p>
                        <p className="truncate text-slate-500">{column.path || "No path set"}</p>
                      </div>
                      <span className="text-[10px] uppercase text-slate-500">
                        {column.required ? "Required" : "Optional"}
                        {!column.enabled ? " · Disabled" : ""}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[11px]">
                      <button
                        type="button"
                        className="font-semibold text-brand-700 hover:underline disabled:text-slate-400"
                        onClick={() => onOpenFile(column.path)}
                        disabled={!column.path}
                      >
                        Open
                      </button>
                      {!column.enabled ? <span className="text-[10px] uppercase text-amber-600">Disabled</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="text-xs text-slate-600">
            <p>
              Transform:{" "}
              {manifest.summary.transformPath ? (
                <button
                  type="button"
                  className="text-brand-700 hover:underline"
                  onClick={() => onOpenFile(manifest.summary.transformPath)}
                >
                  {manifest.summary.transformPath}
                </button>
              ) : (
                "—"
              )}
            </p>
            <p>
              Validators:{" "}
              {manifest.summary.validatorsPath ? (
                <button
                  type="button"
                  className="text-brand-700 hover:underline"
                  onClick={() => onOpenFile(manifest.summary.validatorsPath)}
                >
                  {manifest.summary.validatorsPath}
                </button>
              ) : (
                "—"
              )}
            </p>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500">Manifest file not found ({manifestPath}).</p>
      )}
    </section>
  );
}

function ValidationPanel({
  validation,
  validationError,
  isValidationRunning,
  onValidate,
}: {
  readonly validation: ConfigurationValidateResponse | null;
  readonly validationError: string | null;
  readonly isValidationRunning: boolean;
  readonly onValidate: () => void;
}) {
  const hasIssues = Boolean(validation?.issues?.length);
  return (
    <section>
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Validation</p>
          <p className="text-sm font-semibold text-slate-900">
            {validation ? `Digest ${validation.content_digest ?? "—"}` : "No run yet"}
          </p>
        </div>
        <Button size="sm" onClick={onValidate} isLoading={isValidationRunning}>
          Run
        </Button>
      </header>
      {validationError ? <Alert tone="danger">{validationError}</Alert> : null}
      {isValidationRunning ? <p className="text-sm text-slate-500">Validation running…</p> : null}
      {validation ? (
        <div className="space-y-3 text-sm">
          <p className="text-slate-600">Status: {validation.status}</p>
          {hasIssues ? (
            <div className="space-y-2">
              {validation.issues.map((issue) => (
                <article key={`${issue.path}:${issue.message}`} className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold text-amber-800">{issue.path}</p>
                  <p className="text-sm text-amber-900">{issue.message}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="text-sm text-emerald-700">No issues reported.</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-500">Run validation to populate this panel.</p>
      )}
    </section>
  );
}

function EditorWorkspace({
  tabs,
  activeTab,
  activePath,
  onSelectTab,
  onCloseTab,
  updateContent,
  isSaving,
  dirty,
  editable,
  onSave,
  onRename,
}: {
  readonly tabs: readonly EditorTab[];
  readonly activeTab: EditorTab | null;
  readonly activePath: string | null;
  readonly onSelectTab: (path: string | null) => void;
  readonly onCloseTab: (path: string) => void;
  readonly updateContent: (path: string, value: string) => void;
  readonly isSaving: boolean;
  readonly dirty: boolean;
  readonly editable: boolean;
  readonly onSave: () => void;
  readonly onRename: () => void;
}) {
  return (
    <div className="flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-slate-900/90 shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-800/50 px-3 py-2">
        <div className="flex flex-1 flex-wrap items-center gap-2 overflow-x-auto">
          {tabs.length === 0 ? (
            <p className="text-sm text-slate-300">Select a file to begin editing.</p>
          ) : (
            tabs.map((tab) => (
              <TabChip key={tab.path} tab={tab} active={tab.path === activePath} onSelect={() => onSelectTab(tab.path)} onClose={() => onCloseTab(tab.path)} />
            ))
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onRename} disabled={!activeTab}>
            Rename
          </Button>
          <Button variant="primary" size="sm" disabled={!editable || !dirty || isSaving} isLoading={isSaving} onClick={onSave}>
            Save
          </Button>
        </div>
      </div>
      <div className="flex flex-col border-b border-slate-800/40 px-4 py-3 text-slate-200">
        {activeTab ? (
          <div>
            <p className="text-sm font-semibold text-white">{activeTab.path}</p>
            <p className="text-xs text-slate-400">
              {activeTab.mtime ? `Last modified ${formatTimestamp(activeTab.mtime)}` : null}
              {typeof activeTab.size === "number" ? ` • ${formatBytes(activeTab.size)}` : null}
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-400">Choose a file from the tree to load it into the editor.</p>
        )}
      </div>
      <div className="flex-1 overflow-hidden">
        {!activeTab ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">No file selected.</div>
        ) : activeTab.status === "loading" ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">Loading file…</div>
        ) : activeTab.status === "error" ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-red-200">
            {activeTab.error ?? "Unable to load this file."}
          </div>
        ) : activeTab.encoding !== "utf-8" ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-200">
            Binary files cannot be edited in the browser.
          </div>
        ) : (
          <CodeEditor
            value={activeTab.content}
            onChange={(value) => updateContent(activeTab.path, value)}
            language={detectLanguage(activeTab.path)}
            readOnly={!editable}
            onSaveShortcut={onSave}
          />
        )}
      </div>
      {activeTab?.error && activeTab.status !== "error" ? (
        <div className="border-t border-red-300/40 bg-red-900/20 px-4 py-2 text-sm text-red-200">{activeTab.error}</div>
      ) : null}
    </div>
  );
}

function TabChip({ tab, active, onSelect, onClose }: { readonly tab: EditorTab; readonly active: boolean; readonly onSelect: () => void; readonly onClose: () => void }) {
  const dirty = tab.encoding === "utf-8" && tab.content !== tab.originalContent;
  return (
    <span
      className={clsx(
        "inline-flex items-center overflow-hidden rounded-full border px-3 py-1 text-xs font-medium",
        active ? "border-white/40 bg-white/10 text-white" : "border-transparent bg-white/5 text-slate-200",
      )}
    >
      <button type="button" onClick={onSelect} className="mr-2 truncate">
        {tab.label}
        {dirty ? "*" : null}
      </button>
      <button type="button" onClick={onClose} className="rounded-full px-1 text-slate-300 hover:bg-white/10" aria-label={`Close ${tab.label}`}>
        ×
      </button>
    </span>
  );
}

function FileTree({
  items,
  expanded,
  onToggle,
  onSelect,
  activePath,
}: {
  readonly items: readonly FlattenedNode[];
  readonly expanded: ReadonlySet<string>;
  readonly onToggle: (path: string) => void;
  readonly onSelect: (path: string) => void;
  readonly activePath: string | null;
}) {
  if (items.length === 0) {
    return <div className="flex flex-1 items-center justify-center px-3 py-6 text-sm text-slate-500">No files match this filter.</div>;
  }

  return (
    <div className="flex-1 overflow-y-auto px-2 py-3">
      <ul className="space-y-1">
        {items.map(({ entry, depth }) => {
          const isDir = entry.kind === "dir";
          const isExpanded = isDir && expanded.has(entry.path);
          const isActive = entry.path === activePath;
          const padding = Math.max(depth, 0) * 12 + 8;
          return (
            <li key={entry.path}>
              <button
                type="button"
                onClick={() => (isDir ? onToggle(entry.path) : onSelect(entry.path))}
                className={clsx(
                  "flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left text-sm",
                  isDir ? "text-slate-700 hover:bg-slate-100" : "text-slate-800 hover:bg-white",
                  isActive ? "bg-slate-900/5" : null,
                )}
                style={{ paddingLeft: `${padding}px` }}
              >
                {isDir ? (
                  <span className="text-xs text-slate-500">{isExpanded ? "▾" : entry.has_children ? "▸" : "•"}</span>
                ) : (
                  <span className="text-xs text-slate-400">•</span>
                )}
                <span className="truncate font-medium">{entry.name || entry.path || "(root)"}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RenameDialog({
  path,
  value,
  onChange,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: {
  readonly path: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly onClose: () => void;
  readonly onSubmit: (event: React.FormEvent) => void;
  readonly isSubmitting: boolean;
  readonly error: string | null;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
        <header>
          <p className="text-xs uppercase tracking-wide text-slate-500">Rename file</p>
          <p className="text-sm text-slate-500">{path}</p>
        </header>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">New path</label>
          <Input value={value} onChange={(event) => onChange(event.target.value)} className="mt-1" autoFocus />
        </div>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting} disabled={value.trim().length === 0}>
            Rename
          </Button>
        </div>
      </form>
    </div>
  );
}

function buildFileTree(entries: readonly FileEntry[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  entries.forEach((entry) => {
    map.set(entry.path, { entry, children: [] });
  });
  const roots: TreeNode[] = [];
  entries.forEach((entry) => {
    const node = map.get(entry.path);
    if (!node) {
      return;
    }
    if (!entry.parent) {
      roots.push(node);
      return;
    }
    const parent = map.get(entry.parent);
    if (!parent) {
      roots.push(node);
      return;
    }
    parent.children.push(node);
  });
  sortTreeNodes(roots);
  return roots;
}

function sortTreeNodes(nodes: TreeNode[]) {
  nodes.sort((a, b) => {
    if (a.entry.kind !== b.entry.kind) {
      return a.entry.kind === "dir" ? -1 : 1;
    }
    return a.entry.name.localeCompare(b.entry.name);
  });
  nodes.forEach((node) => sortTreeNodes(node.children));
}

function flattenTree(nodes: readonly TreeNode[], expanded: ReadonlySet<string>, visibleSet: Set<string> | null): FlattenedNode[] {
  const result: FlattenedNode[] = [];
  const walk = (items: readonly TreeNode[]) => {
    items.forEach((node) => {
      if (visibleSet && !visibleSet.has(node.entry.path)) {
        return;
      }
      result.push({ entry: node.entry, depth: Math.max(node.entry.depth, 0) });
      if (node.entry.kind === "dir" && expanded.has(node.entry.path)) {
        walk(node.children);
      }
    });
  };
  walk(nodes);
  return result;
}

function deriveVisibleSet(entries: readonly FileEntry[], query: string): Set<string> | null {
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) {
    return null;
  }
  const matches = new Set<string>();
  const parentMap = new Map(entries.map((entry) => [entry.path, entry.parent ?? ""]));
  entries.forEach((entry) => {
    if (entry.path.toLowerCase().includes(trimmed) || entry.name.toLowerCase().includes(trimmed)) {
      matches.add(entry.path);
      let parent = entry.parent ?? "";
      while (parent) {
        matches.add(parent);
        parent = parentMap.get(parent) ?? "";
      }
    }
  });
  if (matches.size === 0) {
    return new Set();
  }
  return matches;
}

function parseManifestFile(file: FileReadJson | null): ManifestParseResult {
  if (!file) {
    return { summary: null, error: null };
  }
  if (file.encoding !== "utf-8") {
    return { summary: null, error: "Manifest file is not UTF-8 encoded." };
  }
  try {
    const raw = JSON.parse(file.content ?? "{}");
    const columns: ManifestColumnSummary[] = Array.isArray(raw.columns)
      ? raw.columns.map((column: Record<string, unknown>) => ({
          key: String(column.key ?? column.label ?? column.path ?? "column"),
          label: String(column.label ?? column.key ?? column.path ?? "Column"),
          path: String(column.path ?? ""),
          required: Boolean(column.required),
          enabled: column.enabled === undefined ? true : Boolean(column.enabled),
        }))
      : [];
    const summary: ManifestSummary = {
      name: typeof raw.name === "string" && raw.name.trim().length > 0 ? raw.name : "Configuration manifest",
      columns,
      transformPath: raw.table?.transform?.path ?? null,
      validatorsPath: raw.table?.validators?.path ?? null,
    };
    return { summary, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to parse manifest.";
    return { summary: null, error: message };
  }
}

function detectLanguage(path: string | null) {
  if (!path) {
    return "plaintext";
  }
  if (path.endsWith(".py")) {
    return "python";
  }
  if (path.endsWith(".json")) {
    return "json";
  }
  if (path.endsWith(".toml")) {
    return "toml";
  }
  if (path.endsWith(".env")) {
    return "shell";
  }
  return "plaintext";
}

function formatTimestamp(value?: string | Date | null) {
  if (!value) {
    return "";
  }
  try {
    const date = typeof value === "string" ? new Date(value) : value;
    return date.toLocaleString();
  } catch {
    return String(value);
  }
}

function formatBytes(value?: number | null) {
  if (!value || Number.isNaN(value)) {
    return "";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
