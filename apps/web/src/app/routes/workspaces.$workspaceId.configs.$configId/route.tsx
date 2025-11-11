import { Fragment, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import clsx from "clsx";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";
import { Input } from "@ui/input";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  useConfigFilesQuery,
  useConfigQuery,
  useRenameConfigFileMutation,
  useValidateConfigurationMutation,
} from "@shared/configs";
import { useConfigEditorState } from "./useConfigEditorState";
import type { EditorTab } from "./useConfigEditorState";
import type { ConfigurationValidateResponse, FileEntry } from "@shared/configs";

interface TreeNode {
  readonly entry: FileEntry;
  readonly children: TreeNode[];
}

interface FlattenedNode {
  readonly entry: FileEntry;
  readonly depth: number;
}

export default function WorkspaceConfigRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const filesQuery = useConfigFilesQuery({ workspaceId: workspace.id, configId, depth: "infinity", enabled: Boolean(configId) });
  const editor = useConfigEditorState({ workspaceId: workspace.id, configId, onSaved: () => void filesQuery.refetch() });
  const validateConfig = useValidateConfigurationMutation(workspace.id, configId);
  const renameFile = useRenameConfigFileMutation(workspace.id, configId);

  const [fileFilter, setFileFilter] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(["", "src/ade_config/", "assets/"]));
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [insightsCollapsed, setInsightsCollapsed] = useState(false);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

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
  const treeItems = useMemo(
    () => flattenTree(tree, expanded, visibleSet),
    [tree, expanded, visibleSet],
  );

  const editable = configData?.status === "draft";
  const activeTab = editor.activeTab;
  const dirty = Boolean(activeTab && activeTab.encoding === "utf-8" && activeTab.content !== activeTab.originalContent);

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

  if (!configId) {
    return <PageState title="Select a configuration" description="Choose a configuration to open the builder." />;
  }

  if (configQuery.isLoading || filesQuery.isLoading) {
    return <PageState variant="loading" title="Loading configuration" description="Fetching file tree…" />;
  }

  if (configQuery.isError || !configData) {
    return <PageState variant="error" title="Configuration not found" description="This workspace does not include that configuration." />;
  }

  if (filesQuery.isError || !listing) {
    return <PageState variant="error" title="Unable to load files" description="Ensure the configuration exists on disk and try again." />;
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <BuilderHeader
        configName={configData.display_name}
        status={configData.status}
        updatedAt={configData.updated_at}
        onValidate={() => validateConfig.mutate(undefined)}
        validating={validateConfig.isPending}
      />

      {!editable ? (
        <Alert tone="warning" heading="Read-only configuration">
          This configuration is {configData.status}. Clone or switch to a draft to edit files.
        </Alert>
      ) : null}

      <div className="flex flex-1 gap-4 overflow-hidden">
        <aside
          className={clsx(
            "flex flex-col rounded-2xl border border-slate-200 bg-white shadow-sm transition-all",
            leftCollapsed ? "w-12" : "w-72",
          )}
        >
          <FilePanelHeader
            collapsed={leftCollapsed}
            onToggle={() => setLeftCollapsed((value) => !value)}
            filter={fileFilter}
            onFilterChange={setFileFilter}
            summary={listing.summary}
            generatedAt={listing.generated_at}
            isFetching={filesQuery.isFetching}
          />
          {!leftCollapsed ? (
            <FileTree
              items={treeItems}
              expanded={expanded}
              onToggle={handleToggleNode}
              onSelect={(path) => editor.openTab(path)}
              activePath={editor.activePath}
            />
          ) : null}
        </aside>

        <section className="flex min-w-0 flex-1 flex-col gap-4">
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
        </section>

        <aside
          className={clsx(
            "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all",
            insightsCollapsed ? "w-12" : "w-80",
          )}
        >
          <InsightsPanel
            collapsed={insightsCollapsed}
            onToggle={() => setInsightsCollapsed((value) => !value)}
            validation={validateConfig.data ?? null}
            error={validateConfig.isError ? (validateConfig.error as Error).message : null}
          />
        </aside>
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
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={onValidate} isLoading={validating}>
            Validate
          </Button>
        </div>
      </div>
    </header>
  );
}

function FilePanelHeader({
  collapsed,
  onToggle,
  filter,
  onFilterChange,
  summary,
  generatedAt,
  isFetching,
}: {
  readonly collapsed: boolean;
  readonly onToggle: () => void;
  readonly filter: string;
  readonly onFilterChange: (value: string) => void;
  readonly summary: { files: number; directories: number };
  readonly generatedAt: string;
  readonly isFetching: boolean;
}) {
  return (
    <div className="border-b border-slate-200 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Files</p>
        <Button variant="ghost" size="sm" onClick={onToggle}>
          {collapsed ? "›" : "‹"}
        </Button>
      </div>
      {!collapsed ? (
        <Fragment>
          <Input
            value={filter}
            onChange={(event) => onFilterChange(event.target.value)}
            placeholder="Search"
            className="mt-2"
          />
          <p className="mt-2 text-xs text-slate-500">
            {summary.files} files · {summary.directories} directories
          </p>
          <p className="text-[11px] text-slate-400">Generated {formatTimestamp(generatedAt)}</p>
          {isFetching ? <p className="text-[11px] text-slate-400">Refreshing…</p> : null}
        </Fragment>
      ) : null}
    </div>
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
    return (
      <div className="flex flex-1 items-center justify-center px-3 py-6 text-sm text-slate-500">
        No files match this filter.
      </div>
    );
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
                  isDir
                    ? "text-slate-700 hover:bg-slate-100"
                    : "text-slate-800 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                  isActive ? "bg-white shadow" : null,
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
    <div className="flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
        <div className="flex flex-1 flex-wrap items-center gap-2 overflow-x-auto">
          {tabs.length === 0 ? (
            <p className="text-sm text-slate-500">Select a file to begin editing.</p>
          ) : (
            tabs.map((tab) => (
              <TabChip
                key={tab.path}
                tab={tab}
                active={tab.path === activePath}
                onSelect={() => onSelectTab(tab.path)}
                onClose={() => onCloseTab(tab.path)}
              />
            ))
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onRename} disabled={!activeTab}>
            Rename
          </Button>
          <Button variant="primary" size="sm" disabled={!editable || !dirty || isSaving} isLoading={isSaving} onClick={onSave}>
            Save
          </Button>
        </div>
      </div>
      <div className="flex flex-col border-b border-slate-100 px-4 py-3">
        {activeTab ? (
          <div>
            <p className="text-sm font-semibold text-slate-900">{activeTab.path}</p>
            <p className="text-xs text-slate-500">
              {activeTab.mtime ? `Last modified ${formatTimestamp(activeTab.mtime)}` : null}
              {typeof activeTab.size === "number" ? ` • ${formatBytes(activeTab.size)}` : null}
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Choose a file from the tree to load it into the editor.</p>
        )}
      </div>
      <div className="flex-1 overflow-hidden bg-slate-950/95">
        {!activeTab ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-300">No file selected.</div>
        ) : activeTab.status === "loading" ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-300">Loading file…</div>
        ) : activeTab.status === "error" ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-danger-200">
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
        <div className="border-t border-danger-200 bg-danger-50 px-4 py-2 text-sm text-danger-700">{activeTab.error}</div>
      ) : null}
    </div>
  );
}

function TabChip({
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
  collapsed,
  onToggle,
  validation,
  error,
}: {
  readonly collapsed: boolean;
  readonly onToggle: () => void;
  readonly validation: ConfigurationValidateResponse | null;
  readonly error: string | null;
}) {
  if (collapsed) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <Button variant="ghost" size="sm" onClick={onToggle}>
          ‹
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-slate-500">Validation</p>
        <Button variant="ghost" size="sm" onClick={onToggle}>
          ›
        </Button>
      </div>
      {validation ? (
        <div className="space-y-2 text-sm text-slate-700">
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
        <p className="text-sm text-slate-500">Run validation to compute the digest and surface issues.</p>
      )}
      {error ? <Alert tone="danger">{error}</Alert> : null}
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
  readonly onChange: (next: string) => void;
  readonly onClose: () => void;
  readonly onSubmit: (event: React.FormEvent) => void;
  readonly isSubmitting: boolean;
  readonly error: string | null;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <form className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xl" onSubmit={onSubmit}>
        <div>
          <p className="text-sm font-semibold text-slate-900">Rename file</p>
          <p className="text-xs text-slate-500">{path}</p>
        </div>
        <Input value={value} onChange={(event) => onChange(event.target.value)} autoFocus disabled={isSubmitting} />
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" type="button" onClick={onClose} disabled={isSubmitting}>
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
