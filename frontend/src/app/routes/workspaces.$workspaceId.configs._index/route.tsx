import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input, TextArea } from "@ui/input";
import { Select } from "@ui/select";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  getConfigStatusLabel,
  getConfigStatusToneClasses,
  useActivateConfigMutation,
  useCloneConfigMutation,
  useCreateConfigMutation,
  useDeleteConfigMutation,
  useConfigsQuery,
  useExportConfigMutation,
  useImportConfigMutation,
  useLastOpenedConfig,
  useUpdateConfigMutation,
  type ConfigRecord,
} from "@shared/configs";
import { formatDateTime } from "@shared/dates";
import { downloadBlob } from "@shared/download";

export const handle = { workspaceSectionId: "configurations" } as const;

type StatusMessage = { readonly tone: "success" | "danger" | "info"; readonly message: string };

type ConfigStatus = ConfigRecord["status"];

const STATUS_ORDER: Record<ConfigStatus, number> = {
  active: 0,
  inactive: 1,
  archived: 2,
};

export default function WorkspaceConfigsIndexRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const configsQuery = useConfigsQuery({ workspaceId: workspace.id, statuses: ["all"] });

  const [statusMessage, setStatusMessage] = useState<StatusMessage | null>(null);
  const [createTitle, setCreateTitle] = useState<string>("");
  const [createNote, setCreateNote] = useState<string>("");
  const [cloneSourceId, setCloneSourceId] = useState<string>("");
  const [cloneTitle, setCloneTitle] = useState<string>("");
  const [cloneNote, setCloneNote] = useState<string>("");
  const [cloneError, setCloneError] = useState<string | null>(null);
  const [importTitle, setImportTitle] = useState<string>("");
  const [importNote, setImportNote] = useState<string>("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importInputKey, setImportInputKey] = useState<number>(0);

  const configs = configsQuery.data ?? [];

  const { lastConfigId, remember: rememberConfig, clear: clearLastConfig } = useLastOpenedConfig(workspace.id);
  const lastOpenedConfig = useMemo(() => {
    if (!lastConfigId) return null;
    return configs.find((config) => config.config_id === lastConfigId) ?? null;
  }, [configs, lastConfigId]);

  const sortedConfigs = useMemo(() => {
    return [...configs].sort((a, b) => {
      const orderA = STATUS_ORDER[a.status as ConfigStatus] ?? 99;
      const orderB = STATUS_ORDER[b.status as ConfigStatus] ?? 99;
      if (orderA !== orderB) {
        return orderA - orderB;
      }
      const updatedA = Date.parse(a.updated_at ?? "");
      const updatedB = Date.parse(b.updated_at ?? "");
      if (!Number.isNaN(updatedA) && !Number.isNaN(updatedB)) {
        return updatedB - updatedA;
      }
      return a.title.localeCompare(b.title);
    });
  }, [configs]);

  const createMutation = useCreateConfigMutation(workspace.id, {
    onSuccess: (record) => {
      setStatusMessage({ tone: "success", message: `Created ${record.title}.` });
      setCreateTitle("");
      setCreateNote("");
      rememberConfig(record.config_id);
      navigate(`${record.config_id}/editor`);
    },
    onError: (error) => {
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : "Unable to create configuration.",
      });
    },
  });

  const cloneMutation = useCloneConfigMutation(workspace.id, {
    onSuccess: (record) => {
      setStatusMessage({ tone: "success", message: `Cloned ${record.title}.` });
      setCloneSourceId("");
      setCloneTitle("");
      setCloneNote("");
      setCloneError(null);
      rememberConfig(record.config_id);
      navigate(`${record.config_id}/editor`);
    },
    onError: (error, variables) => {
      const targetId = variables?.sourceId;
      const targetConfig = targetId ? configs.find((config) => config.config_id === targetId) : null;
      const name = targetConfig?.title ?? "configuration";
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : `Unable to clone ${name}.`,
      });
    },
  });

  const importMutation = useImportConfigMutation(workspace.id, {
    onSuccess: (record) => {
      setStatusMessage({ tone: "success", message: `Imported ${record.title}.` });
      setImportTitle("");
      setImportNote("");
      setImportFile(null);
      setImportError(null);
      setImportInputKey((value) => value + 1);
      rememberConfig(record.config_id);
      navigate(`${record.config_id}/editor`);
    },
    onError: (error) => {
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : "Unable to import configuration.",
      });
    },
  });

  const activateMutation = useActivateConfigMutation(workspace.id, {
    onSuccess: (record) => {
      setStatusMessage({ tone: "success", message: `Activated ${record.title}.` });
      rememberConfig(record.config_id);
    },
    onError: (error, variables) => {
      const name = variables?.config.title ?? "configuration";
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : `Unable to activate ${name}.`,
      });
    },
  });

  const statusMutation = useUpdateConfigMutation(workspace.id, {
    onSuccess: (record, variables) => {
      const status = variables?.payload.status;
      const message =
        status === "archived"
          ? `Archived ${record.title}.`
          : `Restored ${record.title} to inactive.`;
      setStatusMessage({ tone: "success", message });
    },
    onError: (error, variables) => {
      const status = variables?.payload.status;
      const action = status === "archived" ? "archive" : "restore";
      const name = variables?.config.title ?? "configuration";
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : `Unable to ${action} ${name}.`,
      });
    },
  });

  const deleteMutation = useDeleteConfigMutation(workspace.id, {
    onSuccess: (_result, variables) => {
      const name = variables?.config.title ?? "configuration";
      setStatusMessage({ tone: "success", message: `Deleted ${name}.` });
      if (lastOpenedConfig?.config_id === variables?.config.config_id) {
        clearLastConfig();
      }
    },
    onError: (error, variables) => {
      const name = variables?.config.title ?? "configuration";
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : `Unable to delete ${name}.`,
      });
    },
  });

  const exportMutation = useExportConfigMutation(workspace.id, {
    onSuccess: (result, variables) => {
      downloadBlob(result);
      const name = variables?.config.title ?? "configuration";
      setStatusMessage({ tone: "success", message: `Exported ${name}.` });
    },
    onError: (error, variables) => {
      const name = variables?.config.title ?? "configuration";
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : `Unable to export ${name}.`,
      });
    },
  });

  const isCreating = createMutation.isPending;
  const isCloning = cloneMutation.isPending;
  const isImporting = importMutation.isPending;

  const handleCreateSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage(null);
    const payload = {
      title: createTitle.trim().length > 0 ? createTitle.trim() : null,
      note: createNote.trim().length > 0 ? createNote.trim() : null,
    } as const;
    createMutation.mutate(payload);
  };

  const handleCloneSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage(null);
    if (!cloneSourceId) {
      setCloneError("Select a configuration to clone.");
      return;
    }
    const source = configs.find((config) => config.config_id === cloneSourceId);
    if (!source) {
      setCloneError("Selected configuration could not be found.");
      return;
    }
    setCloneError(null);
    const resolvedTitle = cloneTitle.trim().length > 0 ? cloneTitle.trim() : `${source.title} (copy)`;
    const note = cloneNote.trim().length > 0 ? cloneNote.trim() : null;
    cloneMutation.mutate({ sourceId: source.config_id, title: resolvedTitle, note });
  };

  const handleImportSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage(null);
    if (!importFile) {
      setImportError("Select a zip archive to import.");
      return;
    }
    setImportError(null);
    const title = importTitle.trim().length > 0 ? importTitle.trim() : null;
    const note = importNote.trim().length > 0 ? importNote.trim() : null;
    importMutation.mutate({ archive: importFile, title, note });
  };

  const handleOpenConfig = (config: ConfigRecord) => {
    rememberConfig(config.config_id);
    navigate(`${config.config_id}/editor`);
  };

  const handleActivateConfig = (config: ConfigRecord) => {
    setStatusMessage(null);
    activateMutation.mutate({ config });
  };

  const handleDeleteConfig = (config: ConfigRecord) => {
    if (!window.confirm(`Delete ${config.title}? This action cannot be undone.`)) {
      return;
    }
    setStatusMessage(null);
    deleteMutation.mutate({ config });
  };

  const handleUpdateStatus = (config: ConfigRecord, status: "inactive" | "archived") => {
    setStatusMessage(null);
    statusMutation.mutate({ config, payload: { status } });
  };

  const handleExportConfig = (config: ConfigRecord) => {
    setStatusMessage(null);
    exportMutation.mutate({ config });
  };

  const isActivatingConfig = (config: ConfigRecord) =>
    activateMutation.isPending && activateMutation.variables?.config.config_id === config.config_id;

  const isUpdatingStatus = (config: ConfigRecord, status: "inactive" | "archived") =>
    statusMutation.isPending &&
    statusMutation.variables?.config.config_id === config.config_id &&
    statusMutation.variables?.payload.status === status;

  const isDeletingConfig = (config: ConfigRecord) =>
    deleteMutation.isPending && deleteMutation.variables?.config.config_id === config.config_id;

  const isExportingConfig = (config: ConfigRecord) =>
    exportMutation.isPending && exportMutation.variables?.config.config_id === config.config_id;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Configuration bundles</h1>
        <p className="text-sm text-slate-600">
          Manage file-backed configuration bundles for this workspace. Create new configs, clone existing bundles, import
          archives, and open the editor to update manifests, secrets, or scripts.
        </p>
        {lastOpenedConfig ? (
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => handleOpenConfig(lastOpenedConfig)}
          >
            Resume editing {lastOpenedConfig.title}
          </Button>
        ) : null}
      </header>

      {statusMessage ? <Alert tone={statusMessage.tone}>{statusMessage.message}</Alert> : null}

      {configsQuery.isLoading ? (
        <div className="space-y-2 text-sm text-slate-600">
          <p>Loading configurations…</p>
        </div>
      ) : configsQuery.isError ? (
        <Alert tone="danger">
          Unable to load configurations. {configsQuery.error instanceof Error ? configsQuery.error.message : "Try again later."}
        </Alert>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-4">
            <header className="space-y-1">
              <h2 className="text-lg font-semibold text-slate-900">Existing bundles</h2>
              <p className="text-sm text-slate-500">Activate, archive, export, or delete bundles as needed.</p>
            </header>
            {sortedConfigs.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-white/95 p-4 text-sm text-slate-600 shadow-sm">
                No configurations available yet.
              </div>
            ) : (
              <ul className="space-y-3">
                {sortedConfigs.map((config) => (
                  <li
                    key={config.config_id}
                    className="space-y-3 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-sm"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-semibold text-slate-900">{config.title}</h3>
                          {lastOpenedConfig?.config_id === config.config_id ? (
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                              Last opened
                            </span>
                          ) : null}
                        </div>
                        <p className="text-xs text-slate-500">
                          Updated {formatDateTime(config.updated_at)} • Version {config.version}
                        </p>
                        {config.note ? <p className="text-sm text-slate-600">{config.note}</p> : null}
                      </div>
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-semibold ${getStatusToneClasses(
                          config.status as ConfigStatus,
                        )}`}
                      >
                        {getStatusLabel(config.status as ConfigStatus)}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" variant="primary" size="sm" onClick={() => handleOpenConfig(config)}>
                        Open editor
                      </Button>
                      {config.status !== "active" ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleActivateConfig(config)}
                          disabled={isActivatingConfig(config)}
                        >
                          {isActivatingConfig(config) ? "Activating…" : "Activate"}
                        </Button>
                      ) : null}
                      {config.status === "inactive" ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleUpdateStatus(config, "archived")}
                          disabled={isUpdatingStatus(config, "archived")}
                        >
                          {isUpdatingStatus(config, "archived") ? "Archiving…" : "Archive"}
                        </Button>
                      ) : null}
                      {config.status === "archived" ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleUpdateStatus(config, "inactive")}
                          disabled={isUpdatingStatus(config, "inactive")}
                        >
                          {isUpdatingStatus(config, "inactive") ? "Restoring…" : "Restore"}
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleExportConfig(config)}
                        disabled={isExportingConfig(config)}
                      >
                        {isExportingConfig(config) ? "Exporting…" : "Export"}
                      </Button>
                      {config.status !== "active" ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteConfig(config)}
                          disabled={isDeletingConfig(config)}
                        >
                          {isDeletingConfig(config) ? "Deleting…" : "Delete"}
                        </Button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-4">
            <header className="space-y-1">
              <h2 className="text-lg font-semibold text-slate-900">Create or import</h2>
              <p className="text-sm text-slate-500">Start from the default template, clone an existing bundle, or import an archive.</p>
            </header>

            <form
              className="space-y-3 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-sm"
              onSubmit={handleCreateSubmit}
            >
              <header className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-900">New configuration</h3>
                <p className="text-xs text-slate-500">Creates an inactive bundle using the starter template.</p>
              </header>
              <FormField label="Title" hint="Optional. Defaults to an untitled configuration.">
                <Input
                  value={createTitle}
                  onChange={(event) => setCreateTitle(event.target.value)}
                  placeholder="Starter configuration"
                  disabled={isCreating}
                />
              </FormField>
              <FormField label="Note" hint="Optional description for collaborators.">
                <TextArea
                  value={createNote}
                  onChange={(event) => setCreateNote(event.target.value)}
                  rows={3}
                  disabled={isCreating}
                />
              </FormField>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setCreateTitle("");
                    setCreateNote("");
                  }}
                  disabled={isCreating}
                >
                  Clear
                </Button>
                <Button type="submit" variant="primary" size="sm" disabled={isCreating}>
                  {isCreating ? "Creating…" : "Create"}
                </Button>
              </div>
            </form>

            <form
              className="space-y-3 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-sm"
              onSubmit={handleCloneSubmit}
            >
              <header className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-900">Clone configuration</h3>
                <p className="text-xs text-slate-500">Copies files and manifest into a new inactive bundle.</p>
              </header>
              <FormField label="Source configuration" required error={cloneError ?? undefined}>
                <Select
                  value={cloneSourceId}
                  onChange={(event) => {
                    setCloneSourceId(event.target.value);
                    setCloneError(null);
                    const selected = configs.find((config) => config.config_id === event.target.value);
                    if (selected && cloneTitle.trim().length === 0) {
                      setCloneTitle(`${selected.title} (copy)`);
                    }
                  }}
                  disabled={isCloning || configs.length === 0}
                >
                  <option value="">Select configuration</option>
                  {configs.map((config) => (
                    <option key={config.config_id} value={config.config_id}>
                      {config.title} · {getStatusLabel(config.status as ConfigStatus)}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label="Title" required>
                <Input
                  value={cloneTitle}
                  onChange={(event) => setCloneTitle(event.target.value)}
                  placeholder="My cloned configuration"
                  disabled={isCloning || !cloneSourceId}
                />
              </FormField>
              <FormField label="Note" hint="Optional">
                <TextArea
                  value={cloneNote}
                  onChange={(event) => setCloneNote(event.target.value)}
                  rows={3}
                  disabled={isCloning}
                />
              </FormField>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setCloneSourceId("");
                    setCloneTitle("");
                    setCloneNote("");
                    setCloneError(null);
                  }}
                  disabled={isCloning}
                >
                  Clear
                </Button>
                <Button type="submit" variant="primary" size="sm" disabled={isCloning || !cloneSourceId}>
                  {isCloning ? "Cloning…" : "Clone"}
                </Button>
              </div>
            </form>

            <form
              className="space-y-3 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-sm"
              onSubmit={handleImportSubmit}
            >
              <header className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-900">Import configuration</h3>
                <p className="text-xs text-slate-500">Upload a zip archive exported from ADE.</p>
              </header>
              <FormField label="Archive (.zip)" required error={importError ?? undefined}>
                <Input
                  key={importInputKey}
                  type="file"
                  accept=".zip"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    setImportFile(file);
                    setImportError(null);
                    if (file && importTitle.trim().length === 0) {
                      const nameWithoutExtension = file.name.replace(/\.zip$/i, "");
                      setImportTitle(nameWithoutExtension);
                    }
                  }}
                  disabled={isImporting}
                />
              </FormField>
              <FormField label="Title" hint="Optional override for the imported bundle title.">
                <Input
                  value={importTitle}
                  onChange={(event) => setImportTitle(event.target.value)}
                  placeholder="Imported configuration"
                  disabled={isImporting}
                />
              </FormField>
              <FormField label="Note" hint="Optional">
                <TextArea
                  value={importNote}
                  onChange={(event) => setImportNote(event.target.value)}
                  rows={3}
                  disabled={isImporting}
                />
              </FormField>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setImportTitle("");
                    setImportNote("");
                    setImportFile(null);
                    setImportError(null);
                    setImportInputKey((value) => value + 1);
                  }}
                  disabled={isImporting}
                >
                  Clear
                </Button>
                <Button type="submit" variant="primary" size="sm" disabled={isImporting}>
                  {isImporting ? "Importing…" : "Import"}
                </Button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
