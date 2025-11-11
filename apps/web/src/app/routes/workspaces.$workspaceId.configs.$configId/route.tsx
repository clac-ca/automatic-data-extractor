import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router";
import clsx from "clsx";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  useConfigFilesQuery,
  useConfigQuery,
  useValidateConfigurationMutation,
  type ConfigFileEntry,
  type ConfigurationValidateResponse,
} from "@shared/configs";

import { useConfigEditorState, type EditorTab } from "./useConfigEditorState";

export default function WorkspaceConfigRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const filesQuery = useConfigFilesQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const editor = useConfigEditorState({
    workspaceId: workspace.id,
    configId,
    onSaved: () => {
      void filesQuery.refetch();
    },
  });

  const [validationResult, setValidationResult] = useState<ConfigurationValidateResponse | null>(null);
  const validateConfig = useValidateConfigurationMutation(workspace.id, configId);
  const initialFileOpened = useRef(false);

  const { openTab, tabs, activePath, closeTab, setActivePath, updateContent, saveActiveTab, isSaving } = editor;

  useEffect(() => {
    if (!filesQuery.data || tabs.length > 0 || initialFileOpened.current) {
      return;
    }
    const entries = filesQuery.data.entries.filter((entry) => entry.type === "file");
    const preferred = entries.find((entry) => entry.path === "manifest.json") ?? entries[0];
    if (preferred) {
      initialFileOpened.current = true;
      openTab(preferred.path);
    }
  }, [filesQuery.data, openTab, tabs.length]);

  const handleValidate = () => {
    setValidationResult(null);
    validateConfig.mutate(undefined, {
      onSuccess: setValidationResult,
    });
  };

  if (!configId) {
    return <PageState title="Select a configuration" description="Choose a configuration from the list to open the builder." />;
  }

  if (configQuery.isLoading || filesQuery.isLoading) {
    return <PageState variant="loading" title="Loading configuration" description="Fetching configuration metadata and file tree…" />;
  }

  if (configQuery.isError || !configQuery.data) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="This workspace does not include a configuration with that identifier."
      />
    );
  }

  if (filesQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load files"
        description="Ensure this configuration exists on disk and try again."
      />
    );
  }

  const fileEntries = filesQuery.data?.entries ?? [];
  const editable = configQuery.data.status === "draft";

  return (
    <div className="flex h-full flex-col gap-6">
      <BuilderHeader
        configName={configQuery.data.display_name}
        status={configQuery.data.status}
        updatedAt={configQuery.data.updated_at}
        onValidate={handleValidate}
        validating={validateConfig.isPending}
      />

      {!editable ? (
        <Alert tone="warning" heading="Read-only configuration">
          This configuration is {configQuery.data.status}. Duplicate or switch to a draft to continue editing.
        </Alert>
      ) : null}

      <div className="flex flex-1 gap-4 overflow-hidden">
        <FileTreePanel entries={fileEntries} activePath={activePath} onOpen={openTab} />
        <EditorWorkspace
          tabs={tabs}
          activePath={activePath}
          onSelectTab={setActivePath}
          onCloseTab={closeTab}
          onChangeContent={updateContent}
          onSave={saveActiveTab}
          isSaving={isSaving}
          editable={editable}
        />
        <InsightsPanel
          validation={validationResult}
          lastRunAt={validationResult?.content_digest ? new Date().toISOString() : null}
          validationError={validateConfig.isError ? (validateConfig.error as Error).message : null}
        />
      </div>
    </div>
  );
}

function BuilderHeader({
  configName,
  status,
  updatedAt,
  onValidate,
  validating,
}: {
  readonly configName: string;
  readonly status: string;
  readonly updatedAt: string;
  readonly onValidate: () => void;
  readonly validating: boolean;
}) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-slate-500">Configuration</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">{configName}</h1>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
              {status}
            </span>
          </div>
          <p className="text-sm text-slate-500">Updated {formatTimestamp(updatedAt)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" size="sm" onClick={onValidate} isLoading={validating}>
            Validate
          </Button>
        </div>
      </div>
    </header>
  );
}

function FileTreePanel({
  entries,
  activePath,
  onOpen,
}: {
  readonly entries: readonly ConfigFileEntry[];
  readonly activePath: string | null;
  readonly onOpen: (path: string) => void;
}) {
  const items = useMemo(() => buildTree(entries), [entries]);

  if (items.length === 0) {
    return (
      <section className="w-64 rounded-2xl border border-dashed border-slate-200 bg-white/60 p-4 text-sm text-slate-500">
        No editable files were found.
      </section>
    );
  }

  return (
    <section className="flex w-64 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white/80 shadow-sm">
      <div className="border-b border-slate-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Files
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-1">
          {items.map((item) => (
            <FileTreeNode key={item.path} node={item} activePath={activePath} onOpen={onOpen} />
          ))}
        </ul>
      </div>
    </section>
  );
}

interface TreeNode {
  readonly path: string;
  readonly label: string;
  readonly type: "file" | "dir";
  readonly depth: number;
}

function buildTree(entries: readonly ConfigFileEntry[]): TreeNode[] {
  return [...entries]
    .filter((entry) => entry.type === "file" || entry.type === "dir")
    .sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "dir" ? -1 : 1;
      }
      return a.path.localeCompare(b.path);
    })
    .map((entry) => ({
      path: entry.path,
      label: entry.path.split("/").pop() ?? entry.path,
      type: entry.type,
      depth: Math.max(0, entry.path.split("/").length - 1),
    }));
}

function FileTreeNode({
  node,
  activePath,
  onOpen,
}: {
  readonly node: TreeNode;
  readonly activePath: string | null;
  readonly onOpen: (path: string) => void;
}) {
  const isActive = node.type === "file" && node.path === activePath;
  return (
    <li>
      <button
        type="button"
        disabled={node.type !== "file"}
        onClick={() => node.type === "file" && onOpen(node.path)}
        className={clsx(
          "flex w-full items-center gap-2 rounded-xl px-3 py-1.5 text-left text-sm transition",
          node.type === "file"
            ? "text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            : "text-slate-500",
          isActive ? "bg-slate-100" : null,
        )}
        style={{ paddingLeft: `${node.type === "file" ? node.depth * 12 + 12 : 12}px` }}
      >
        <span className="text-xs uppercase text-slate-400">{node.type === "dir" ? "DIR" : fileExtensionLabel(node.label)}</span>
        <span className="truncate font-medium">{node.type === "dir" ? `${node.label}/` : node.label}</span>
      </button>
    </li>
  );
}

function EditorWorkspace({
  tabs,
  activePath,
  onSelectTab,
  onCloseTab,
  onChangeContent,
  onSave,
  isSaving,
  editable,
}: {
  readonly tabs: readonly EditorTab[];
  readonly activePath: string | null;
  readonly onSelectTab: (path: string | null) => void;
  readonly onCloseTab: (path: string) => void;
  readonly onChangeContent: (path: string, next: string) => void;
  readonly onSave: () => void;
  readonly isSaving: boolean;
  readonly editable: boolean;
}) {
  const activeTab = tabs.find((tab) => tab.path === activePath) ?? null;
  const dirty = activeTab && activeTab.encoding === "utf-8" && activeTab.content !== activeTab.originalContent;
  const readOnly = !editable || activeTab?.encoding !== "utf-8";

  return (
    <section className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
        <div className="flex flex-1 items-center gap-2 overflow-x-auto">
          {tabs.length === 0 ? (
            <p className="text-sm text-slate-500">Select a file from the sidebar to begin editing.</p>
          ) : (
            tabs.map((tab) => (
              <EditorTabChip
                key={tab.path}
                tab={tab}
                active={tab.path === activePath}
                onSelect={() => onSelectTab(tab.path)}
                onClose={() => onCloseTab(tab.path)}
              />
            ))
          )}
        </div>
        <Button
          size="sm"
          onClick={onSave}
          disabled={!activeTab || readOnly || !dirty || isSaving}
          isLoading={isSaving}
        >
          Save
        </Button>
      </div>
      <div className="flex-1 overflow-hidden bg-slate-950/95">
        {!activeTab ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-300">
            Choose a file to begin editing.
          </div>
        ) : activeTab.status === "loading" ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-300">Loading file…</div>
        ) : activeTab.status === "error" ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-200">
            {activeTab.error ?? "Unable to load this file."}
          </div>
        ) : activeTab.encoding === "base64" ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-200">
            Binary files can’t be edited in the browser. Download and edit them locally.
          </div>
        ) : (
          <CodeEditor
            value={activeTab.content}
            onChange={(value) => activeTab && onChangeContent(activeTab.path, value)}
            language={detectLanguage(activeTab.path)}
            readOnly={readOnly}
            onSaveShortcut={onSave}
          />
        )}
      </div>
      {activeTab?.error ? (
        <div className="border-t border-danger-200 bg-danger-50 px-4 py-2 text-sm text-danger-700">{activeTab.error}</div>
      ) : null}
    </section>
  );
}

function EditorTabChip({
  tab,
  active,
  onSelect,
  onClose,
}: {
  readonly tab: EditorTab;
  readonly active: boolean;
  readonly onSelect: () => void;
  readonly onClose: () => void;
}) {
  const dirty = tab.encoding === "utf-8" && tab.content !== tab.originalContent;
  return (
    <span
      className={clsx(
        "inline-flex items-center overflow-hidden rounded-full border px-3 py-1 text-xs font-medium",
        active ? "border-brand-500 bg-brand-50 text-brand-700" : "border-transparent bg-slate-100 text-slate-600",
      )}
    >
      <button type="button" onClick={onSelect} className="mr-2 truncate">
        {tab.label}
        {dirty ? "*" : null}
      </button>
      <button
        type="button"
        onClick={onClose}
        className="rounded-full px-1 text-slate-500 hover:bg-black/10"
        aria-label={`Close ${tab.label}`}
      >
        ×
      </button>
    </span>
  );
}

function InsightsPanel({
  validation,
  lastRunAt,
  validationError,
}: {
  readonly validation: ConfigurationValidateResponse | null;
  readonly lastRunAt: string | null;
  readonly validationError: string | null;
}) {
  return (
    <section className="flex w-80 flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Validation</p>
        {validation ? (
          <div className="mt-2 space-y-1 text-sm text-slate-700">
            <p className="font-semibold text-slate-900">Digest {validation.content_digest ?? "—"}</p>
            {validation.issues.length === 0 ? (
              <p className="text-sm text-success-700">No issues detected.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-4 text-sm text-danger-700">
                {validation.issues.map((issue) => (
                  <li key={`${issue.path}:${issue.message}`}>
                    <span className="font-medium">{issue.path}</span>: {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Run validation to compute the digest and surface issues.</p>
        )}
      </div>
      {lastRunAt ? <p className="text-xs text-slate-400">Last run {formatTimestamp(lastRunAt)}</p> : null}
      {validationError ? <Alert tone="danger">{validationError}</Alert> : null}
    </section>
  );
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

function fileExtensionLabel(name: string) {
  const parts = name.split(".");
  return parts.length > 1 ? parts.pop()?.toUpperCase() ?? "TXT" : "TXT";
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "";
  }
  try {
    const date = new Date(value);
    return date.toLocaleString();
  } catch {
    return value;
  }
}
