import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import clsx from "clsx";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  useConfigFileQuery,
  useConfigFilesQuery,
  useConfigsQuery,
  useSaveConfigFileMutation,
  type ConfigFileEntry,
  type ConfigRecord,
} from "@shared/configs";

export default function WorkspaceConfigRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";

  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });
  const activeConfig = useMemo<ConfigRecord | null>(
    () => configsQuery.data?.find((config) => config.config_id === configId) ?? null,
    [configsQuery.data, configId],
  );

  const filesQuery = useConfigFilesQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  useEffect(() => {
    if (!filesQuery.data) {
      return;
    }
    const files = filesQuery.data.entries.filter((entry) => entry.type === "file");
    if (files.length === 0) {
      setSelectedPath(null);
      return;
    }
    if (selectedPath && files.some((entry) => entry.path === selectedPath)) {
      return;
    }
    const preferred = files.find((entry) => entry.path === "manifest.json") ?? files[0];
    setSelectedPath(preferred?.path ?? null);
  }, [filesQuery.data, selectedPath]);

  const fileQuery = useConfigFileQuery({
    workspaceId: workspace.id,
    configId,
    path: selectedPath,
    enabled: Boolean(selectedPath),
  });

  const [editorValue, setEditorValue] = useState("");
  const [currentEtag, setCurrentEtag] = useState<string | null>(null);
  const [currentEncoding, setCurrentEncoding] = useState<"utf-8" | "base64" | null>(null);

  useEffect(() => {
    const info = fileQuery.data;
    if (!info) {
      setCurrentEncoding(null);
      setEditorValue("");
      setCurrentEtag(null);
      return;
    }
    setCurrentEncoding(info.encoding);
    if (info.encoding === "utf-8") {
      setEditorValue(info.content);
    } else {
      setEditorValue("");
    }
    setCurrentEtag(info.etag ?? null);
  }, [fileQuery.data]);

  const dirty = fileQuery.data && fileQuery.data.encoding === "utf-8" ? editorValue !== fileQuery.data.content : false;
  const saveFile = useSaveConfigFileMutation(workspace.id, configId);

  const handleSave = () => {
    if (!selectedPath || currentEncoding !== "utf-8") {
      return;
    }
    saveFile.mutate({
      path: selectedPath,
      content: editorValue,
      etag: currentEtag,
    });
  };

  if (!configId) {
    return <PageState title="Select a configuration" description="Choose a configuration from the list to open the builder." />;
  }

  if (configsQuery.isLoading || filesQuery.isLoading) {
    return <PageState variant="loading" title="Loading configuration" description="Fetching configuration metadata and file tree…" />;
  }

  if (configsQuery.isError) {
    return <PageState variant="error" title="Unable to load configurations" description="Try refreshing the page or check your network connection." />;
  }

  if (!activeConfig) {
    return <PageState variant="error" title="Configuration not found" description="This workspace does not include a configuration with that identifier." />;
  }

  if (filesQuery.isError) {
    return <PageState variant="error" title="Unable to load files" description="Ensure the configuration exists on disk and try again." />;
  }

  const hasFiles = (filesQuery.data?.entries ?? []).some((entry) => entry.type === "file");

  return (
    <div className="flex h-full flex-col gap-6">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-slate-500">Configuration</p>
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{activeConfig.display_name}</h1>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            {activeConfig.status}
          </span>
          <p className="text-sm text-slate-500">Updated {formatTimestamp(activeConfig.updated_at)}</p>
        </div>
      </header>

      {!hasFiles ? (
        <PageState
          title="No editable files found"
          description="Templates include manifest files and detectors under src/ade_config/. Ensure the configuration was copied correctly."
        />
      ) : (
        <div className="flex min-h-[520px] flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <aside className="flex w-64 flex-col border-r border-slate-100 bg-slate-50">
            <div className="border-b border-slate-200 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Files</p>
            </div>
            <FileList
              entries={filesQuery.data?.entries ?? []}
              selectedPath={selectedPath}
              onSelect={(path) => setSelectedPath(path)}
            />
          </aside>

          <section className="flex flex-1 flex-col">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
              <div>
                {selectedPath ? (
                  <>
                    <p className="font-semibold text-slate-900">{selectedPath}</p>
                    <p className="text-xs text-slate-500">
                      {fileQuery.data?.mtime ? `Last modified ${formatTimestamp(fileQuery.data.mtime)}` : ""}
                      {fileQuery.data?.size ? ` • ${formatBytes(fileQuery.data.size)}` : ""}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-slate-500">Select a file to view its contents.</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {saveFile.isError ? (
                  <Alert tone="danger" className="px-3 py-2 text-xs" heading="Save failed">
                    {(saveFile.error as Error).message ?? "Unable to save file."}
                  </Alert>
                ) : null}
                <Button
                  variant="primary"
                  disabled={!dirty || saveFile.isPending || currentEncoding !== "utf-8"}
                  isLoading={saveFile.isPending}
                  onClick={handleSave}
                >
                  Save
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-hidden bg-slate-900/95">
              {selectedPath ? (
                fileQuery.isLoading ? (
                  <div className="flex h-full items-center justify-center text-sm text-slate-300">Loading file…</div>
                ) : fileQuery.isError ? (
                  <div className="flex h-full items-center justify-center">
                    <PageState
                      variant="error"
                      title="Unable to load file"
                      description="The file may have been deleted or moved. Refresh the tree and try again."
                    />
                  </div>
                ) : currentEncoding !== "utf-8" ? (
                  <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-200">
                    Binary files (base64) aren’t editable in the browser. Download and modify them via the CLI.
                  </div>
                ) : (
                  <CodeEditor
                    value={editorValue}
                    onChange={setEditorValue}
                    language={detectLanguage(selectedPath)}
                    onSaveShortcut={handleSave}
                  />
                )
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-slate-300">
                  Choose a file from the sidebar to begin editing.
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function FileList({
  entries,
  selectedPath,
  onSelect,
}: {
  readonly entries: readonly ConfigFileEntry[];
  readonly selectedPath: string | null;
  readonly onSelect: (path: string) => void;
}) {
  const ordered = useMemo(() => sortEntries(entries), [entries]);

  return (
    <div className="flex-1 overflow-y-auto px-2 py-2">
      <ul className="space-y-1">
        {ordered.map((entry) => {
          const depth = Math.max(0, entry.path.split("/").length - 1);
          const isSelected = entry.type === "file" && entry.path === selectedPath;
          const label = entry.path.split("/").pop() ?? entry.path;
          return (
            <li key={entry.path}>
              <button
                type="button"
                disabled={entry.type !== "file"}
                onClick={() => entry.type === "file" && onSelect(entry.path)}
                className={clsx(
                  "flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm transition",
                  entry.type === "file"
                    ? "text-slate-800 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    : "text-slate-500",
                  isSelected ? "bg-white shadow" : "",
                )}
                style={{ paddingLeft: `${12 + depth * 12}px` }}
              >
                <span className="text-xs uppercase text-slate-400">
                  {entry.type === "dir" ? "DIR" : fileExtensionLabel(label)}
                </span>
                <span className="truncate font-medium">
                  {entry.type === "dir" ? `${label}/` : label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function sortEntries(entries: readonly ConfigFileEntry[]) {
  return [...entries].sort((a, b) => {
    if (a.type !== b.type) {
      return a.type === "dir" ? -1 : 1;
    }
    return a.path.localeCompare(b.path);
  });
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

function formatBytes(value?: number) {
  if (!value) {
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
