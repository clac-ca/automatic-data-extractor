import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, MouseEvent as ReactMouseEvent } from "react";

import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ContextMenu, type ContextMenuItem } from "@/components/ui/context-menu-simple";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { PageState } from "@/components/layout";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { exportConfiguration, validateConfiguration } from "@/api/configurations/api";
import {
  useArchiveConfigurationMutation,
  useConfigurationsQuery,
  useCreateConfigurationMutation,
  useDuplicateConfigurationMutation,
  useImportConfigurationMutation,
  useMakeActiveConfigurationMutation,
} from "@/pages/Workspace/hooks/configurations";
import type { ConfigurationRecord } from "@/types/configurations";
import { useNotifications } from "@/providers/notifications";
import { buildLastSelectionStorageKey, createLastSelectionStorage, persistLastSelection, type LastSelection } from "./storage";
import { StatusPill } from "./components/StatusPill";
import { normalizeConfigStatus, sortByUpdatedDesc, suggestDuplicateName } from "./utils/configs";

const DEFAULT_TEMPLATE_LABEL = "Default template";

const buildConfigDetailPath = (workspaceId: string, configId: string) =>
  `/workspaces/${workspaceId}/config-builder/${encodeURIComponent(configId)}`;

export default function ConfigBuilderScreen() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const { notifyToast } = useNotifications();
  const storageKey = useMemo(() => buildLastSelectionStorageKey(workspace.id), [workspace.id]);
  const storage = useMemo(() => createLastSelectionStorage(workspace.id), [workspace.id]);
  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const { refetch: refetchConfigurations } = configurationsQuery;
  const createConfig = useCreateConfigurationMutation(workspace.id);
  const importConfig = useImportConfigurationMutation(workspace.id);
  const makeActiveConfig = useMakeActiveConfigurationMutation(workspace.id);
  const archiveConfig = useArchiveConfigurationMutation(workspace.id);
  const duplicateConfig = useDuplicateConfigurationMutation(workspace.id);

  const [displayName, setDisplayName] = useState(() => `${workspace.name} Config`);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [importDisplayName, setImportDisplayName] = useState(() => `${workspace.name} Import`);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [lastSelection, setLastSelection] = useState<LastSelection>(() => storage.get<LastSelection>());
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const lastWorkspaceRef = useRef<{ id: string; name: string } | null>(null);

  const configurations = useMemo(
    () =>
      (configurationsQuery.data?.items ?? []).filter(
        (config) => !("deleted_at" in config && (config as { deleted_at?: string | null }).deleted_at),
      ),
    [configurationsQuery.data],
  );
  const normalizedStatuses = useMemo(() => {
    const map = new Map<string, string>();
    for (const config of configurations) {
      map.set(config.id, normalizeConfigStatus(config.status));
    }
    return map;
  }, [configurations]);
  const activeConfiguration = useMemo(() => {
    for (const config of configurations) {
      if (normalizedStatuses.get(config.id) === "active") {
        return config;
      }
    }
    return null;
  }, [configurations, normalizedStatuses]);
  const draftConfigurations = useMemo(
    () =>
      configurations
        .filter((config) => normalizedStatuses.get(config.id) === "draft")
        .sort((a, b) => sortByUpdatedDesc(a.updated_at, b.updated_at)),
    [configurations, normalizedStatuses],
  );
  const archivedConfigurations = useMemo(
    () =>
      configurations
        .filter((config) => normalizedStatuses.get(config.id) === "archived")
        .sort((a, b) => sortByUpdatedDesc(a.updated_at, b.updated_at)),
    [configurations, normalizedStatuses],
  );
  const lastOpenedConfig = useMemo(
    () => configurations.find((config) => config.id === lastSelection?.configId) ?? null,
    [configurations, lastSelection],
  );

  const updateLastSelection = useCallback(
    (configId: string | null) => {
      setLastSelection(persistLastSelection(storage, configId));
    },
    [storage],
  );

  useEffect(() => {
    setLastSelection(storage.get<LastSelection>());
  }, [storage]);

  useEffect(() => {
    const previous = lastWorkspaceRef.current;
    const idChanged = previous?.id !== workspace.id;
    const nameChanged = previous?.name !== workspace.name;
    if (!idChanged && !nameChanged) {
      return;
    }
    lastWorkspaceRef.current = { id: workspace.id, name: workspace.name };

    if (idChanged) {
      setDisplayName(`${workspace.name} Config`);
      setValidationError(null);
      setImportDisplayName(`${workspace.name} Import`);
      setImportFile(null);
      setImportError(null);
      if (importInputRef.current) {
        importInputRef.current.value = "";
      }
      return;
    }

    if (nameChanged) {
      setDisplayName((current) => (current === `${previous?.name ?? ""} Config` ? `${workspace.name} Config` : current));
      setImportDisplayName((current) => (current === `${previous?.name ?? ""} Import` ? `${workspace.name} Import` : current));
    }
  }, [workspace.id, workspace.name]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.storageArea !== window.localStorage || event.key !== storageKey) {
        return;
      }
      try {
        setLastSelection(event.newValue ? (JSON.parse(event.newValue) as LastSelection) : null);
      } catch {
        setLastSelection(null);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [storageKey]);

  useEffect(() => {
    if (!lastSelection?.configId) {
      return;
    }
    if (configurations.some((config) => config.id === lastSelection.configId)) {
      return;
    }
    updateLastSelection(null);
  }, [configurations, lastSelection?.configId, updateLastSelection]);

  const handleOpenConfig = useCallback(
    (configId: string) => {
      updateLastSelection(configId);
      navigate(buildConfigDetailPath(workspace.id, configId));
    },
    [navigate, updateLastSelection, workspace.id],
  );

  const handleOpenEditor = useCallback(
    (configId: string) => {
      updateLastSelection(configId);
      navigate(`${buildConfigDetailPath(workspace.id, configId)}/editor`);
    },
    [navigate, updateLastSelection, workspace.id],
  );

  const [contextMenu, setContextMenu] = useState<{ configId: string; x: number; y: number } | null>(null);
  const contextMenuConfig = useMemo(
    () => (contextMenu ? configurations.find((config) => config.id === contextMenu.configId) ?? null : null),
    [configurations, contextMenu],
  );

  const [exportingConfigId, setExportingConfigId] = useState<string | null>(null);
  const handleExportConfig = useCallback(
    async (config: ConfigurationRecord) => {
      setExportingConfigId(config.id);
      try {
        const result = await exportConfiguration(workspace.id, config.id);
        const filename = result.filename ?? `${config.id}.zip`;
        const url = URL.createObjectURL(result.blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
        notifyToast({ title: `Exported ${filename}`, intent: "success", duration: 4000 });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to export configuration.";
        notifyToast({ title: message, intent: "danger", duration: 6000 });
      } finally {
        setExportingConfigId((current) => (current === config.id ? null : current));
      }
    },
    [notifyToast, workspace.id],
  );

  const [duplicateConfigId, setDuplicateConfigId] = useState<string | null>(null);
  const duplicateSource = useMemo(
    () => (duplicateConfigId ? configurations.find((config) => config.id === duplicateConfigId) ?? null : null),
    [configurations, duplicateConfigId],
  );
  const existingNames = useMemo(() => new Set(configurations.map((c) => c.display_name.trim().toLowerCase())), [configurations]);
  const [duplicateName, setDuplicateName] = useState("");
  const [duplicateNameError, setDuplicateNameError] = useState<string | null>(null);
  const openDuplicateDialog = useCallback(
    (config: ConfigurationRecord) => {
      duplicateConfig.reset();
      setDuplicateNameError(null);
      setDuplicateName(suggestDuplicateName(config.display_name, existingNames));
      setDuplicateConfigId(config.id);
    },
    [duplicateConfig, existingNames],
  );

  const [archiveConfigId, setArchiveConfigId] = useState<string | null>(null);
  const archiveTarget = useMemo(
    () => (archiveConfigId ? configurations.find((config) => config.id === archiveConfigId) ?? null : null),
    [archiveConfigId, configurations],
  );

  type MakeActiveDialogState =
    | { stage: "checking" }
    | { stage: "confirm" }
    | { stage: "issues"; issues: readonly { path: string; message: string }[] }
    | { stage: "error"; message: string };
  const [makeActiveConfigId, setMakeActiveConfigId] = useState<string | null>(null);
  const makeActiveTarget = useMemo(
    () => (makeActiveConfigId ? configurations.find((config) => config.id === makeActiveConfigId) ?? null : null),
    [configurations, makeActiveConfigId],
  );
  const makeActiveTargetId = makeActiveTarget?.id ?? null;
  const [makeActiveDialogState, setMakeActiveDialogState] = useState<MakeActiveDialogState | null>(null);

  useEffect(() => {
    if (!makeActiveTargetId) {
      setMakeActiveDialogState(null);
      return;
    }
    let cancelled = false;
    setMakeActiveDialogState({ stage: "checking" });
    void validateConfiguration(workspace.id, makeActiveTargetId)
      .then((result) => {
        if (cancelled) return;
        if (Array.isArray(result.issues) && result.issues.length > 0) {
          setMakeActiveDialogState({ stage: "issues", issues: result.issues });
          return;
        }
        setMakeActiveDialogState({ stage: "confirm" });
      })
      .catch((error) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Unable to validate configuration.";
        setMakeActiveDialogState({ stage: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [makeActiveTargetId, workspace.id]);

  const handleOpenMakeActiveDialog = useCallback(
    (config: ConfigurationRecord) => {
      makeActiveConfig.reset();
      setMakeActiveDialogState({ stage: "checking" });
      setMakeActiveConfigId(config.id);
    },
    [makeActiveConfig],
  );

  const closeMakeActiveDialog = useCallback(() => {
    setMakeActiveConfigId(null);
    setMakeActiveDialogState(null);
  }, []);

  const closeDuplicateDialog = useCallback(() => {
    setDuplicateConfigId(null);
    setDuplicateNameError(null);
  }, []);

  const closeArchiveDialog = useCallback(() => {
    setArchiveConfigId(null);
  }, []);

  const handleConfirmMakeActive = useCallback(() => {
    if (!makeActiveTarget) {
      return;
    }
    makeActiveConfig.mutate(
      { configurationId: makeActiveTarget.id },
      {
        onSuccess() {
          notifyToast({
            title: "Configuration is now active.",
            intent: "success",
            duration: 4000,
          });
          closeMakeActiveDialog();
          void refetchConfigurations();
        },
        onError(error) {
          notifyToast({
            title: error instanceof Error ? error.message : "Unable to make configuration active.",
            intent: "danger",
            duration: 6000,
          });
        },
      },
    );
  }, [closeMakeActiveDialog, makeActiveConfig, makeActiveTarget, notifyToast, refetchConfigurations]);

  const handleConfirmArchive = useCallback(() => {
    if (!archiveTarget) {
      return;
    }
    archiveConfig.mutate(
      { configurationId: archiveTarget.id },
      {
        onSuccess() {
          notifyToast({
            title: "Active configuration archived.",
            intent: "success",
            duration: 4000,
          });
          closeArchiveDialog();
          void refetchConfigurations();
        },
        onError(error) {
          notifyToast({
            title: error instanceof Error ? error.message : "Unable to archive configuration.",
            intent: "danger",
            duration: 6000,
          });
        },
      },
    );
  }, [archiveConfig, archiveTarget, closeArchiveDialog, notifyToast, refetchConfigurations]);

  const handleConfirmDuplicate = useCallback(() => {
    if (!duplicateSource) {
      return;
    }
    const trimmed = duplicateName.trim();
    if (!trimmed) {
      setDuplicateNameError("Enter a name for the new draft configuration.");
      return;
    }
    setDuplicateNameError(null);
    duplicateConfig.mutate(
      { sourceConfigurationId: duplicateSource.id, displayName: trimmed },
      {
        onSuccess(record) {
          updateLastSelection(record.id);
          notifyToast({ title: "Draft created.", intent: "success", duration: 3500 });
          closeDuplicateDialog();
          navigate(`${buildConfigDetailPath(workspace.id, record.id)}/editor`);
        },
        onError(error) {
          const message = error instanceof Error ? error.message : "Unable to duplicate configuration.";
          setDuplicateNameError(message);
        },
      },
    );
  }, [
    closeDuplicateDialog,
    duplicateConfig,
    duplicateName,
    duplicateSource,
    navigate,
    notifyToast,
    updateLastSelection,
    workspace.id,
  ]);

  const openContextMenu = useCallback((event: ReactMouseEvent<HTMLButtonElement>, configId: string) => {
    event.preventDefault();
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    setContextMenu({ configId, x: rect.right + 8, y: rect.bottom });
  }, []);

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuConfig) {
      return [];
    }
    const status = normalizedStatuses.get(contextMenuConfig.id) ?? normalizeConfigStatus(contextMenuConfig.status);
    const isExporting = exportingConfigId === contextMenuConfig.id;
    const items: ContextMenuItem[] = [
      {
        id: "open-editor",
        label: "Open editor",
        onSelect: () => handleOpenEditor(contextMenuConfig.id),
      },
      {
        id: "export",
        label: isExporting ? "Exporting…" : "Export",
        onSelect: () => {
          void handleExportConfig(contextMenuConfig);
        },
        disabled: isExporting,
      },
      {
        id: "duplicate",
        label: "Duplicate to edit",
        onSelect: () => openDuplicateDialog(contextMenuConfig),
        dividerAbove: true,
      },
    ];
    if (status === "active") {
      items.push({
        id: "archive",
        label: "Archive",
        onSelect: () => setArchiveConfigId(contextMenuConfig.id),
        danger: true,
        dividerAbove: true,
      });
    }
    return items;
  }, [
    contextMenuConfig,
    exportingConfigId,
    handleExportConfig,
    handleOpenEditor,
    normalizedStatuses,
    openDuplicateDialog,
  ]);

  const handleImportFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setImportError(null);
    setImportFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  }, []);

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = displayName.trim();
    if (!trimmed) {
      setValidationError("Enter a display name for the configuration.");
      return;
    }
    setValidationError(null);
    createConfig.mutate(
      {
        displayName: trimmed,
        source: { type: "template" },
      },
      {
        onSuccess(record) {
          updateLastSelection(record.id);
          navigate(buildConfigDetailPath(workspace.id, record.id));
        },
      },
    );
  };

  const handleImport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = importDisplayName.trim();
    if (!trimmedName) {
      setImportError("Enter a display name for the imported configuration.");
      return;
    }
    if (!importFile) {
      setImportError("Select a .zip file to import.");
      return;
    }
    setImportError(null);
    importConfig.mutate(
      { displayName: trimmedName, file: importFile },
      {
        onSuccess(record) {
          updateLastSelection(record.id);
          setImportFile(null);
          void configurationsQuery.refetch();
          navigate(buildConfigDetailPath(workspace.id, record.id));
        },
        onError(error) {
          setImportError(error instanceof Error ? error.message : "Unable to import configuration.");
        },
      },
    );
  };

  const creationError = validationError ?? (createConfig.error instanceof Error ? createConfig.error.message : null);
  const canSubmit = displayName.trim().length > 0 && !createConfig.isPending;
  const canImport = importDisplayName.trim().length > 0 && Boolean(importFile) && !importConfig.isPending;
  const renderTemplateField = (disabled: boolean) => (
    <FormField label="Template">
      <Input value={DEFAULT_TEMPLATE_LABEL} readOnly disabled={disabled} />
    </FormField>
  );

  if (configurationsQuery.isLoading) {
    return <PageState variant="loading" title="Loading configurations" description="Fetching workspace configurations…" />;
  }

  if (configurationsQuery.isError) {
    return <PageState variant="error" title="Unable to load configurations" description="Try refreshing the page." />;
  }

  if (configurations.length === 0) {
    return (
      <PageState
        className="mx-auto w-full max-w-xl"
        title="Create your first configuration"
        description="Copy a starter template into this workspace to begin editing detectors, hooks, and manifests."
        action={
          <div className="space-y-6 text-left">
            <form onSubmit={handleCreate} className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-sm">
              <FormField label="Configuration name" required>
                <Input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Membership normalization"
                  disabled={createConfig.isPending}
                />
              </FormField>
              {renderTemplateField(createConfig.isPending)}
              {creationError ? <p className="text-sm font-medium text-destructive">{creationError}</p> : null}
              <Button
                type="submit"
                className="w-full"
                disabled={!canSubmit || createConfig.isPending}
              >
                Create from template
              </Button>
            </form>
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-foreground">Import configuration</h2>
                <p className="text-sm text-muted-foreground">Upload an ADE export (.zip) to create a new draft configuration.</p>
              </div>
              <form onSubmit={handleImport} className="mt-3 space-y-4">
                <FormField label="Configuration name" required>
                  <Input
                    value={importDisplayName}
                    onChange={(event) => setImportDisplayName(event.target.value)}
                    placeholder="Imported configuration"
                    disabled={importConfig.isPending}
                  />
                </FormField>
                <FormField label="Archive (.zip)" required>
                  <Input
                    type="file"
                    ref={importInputRef}
                    accept=".zip"
                    onChange={handleImportFileChange}
                    disabled={importConfig.isPending}
                  />
                  {importFile ? (
                    <p className="mt-1 text-xs text-muted-foreground" aria-live="polite">
                      {importFile.name}
                    </p>
                  ) : null}
                </FormField>
                {importError ? <p className="text-sm font-medium text-destructive">{importError}</p> : null}
                <Button
                  type="submit"
                  className="w-full"
                  disabled={!canImport || importConfig.isPending}
                >
                  Import archive
                </Button>
              </form>
            </div>
          </div>
        }
      />
    );
  }

  return (
    <div className="grid gap-6 p-4 lg:grid-cols-[minmax(0,2fr),minmax(0,1fr)]">
      <section className="space-y-4 rounded-2xl border border-border bg-card p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Configurations</h1>
            <p className="text-sm text-muted-foreground">
              Manage draft, active, and archived configurations for this workspace.
            </p>
          </div>
          {lastOpenedConfig ? (
            <Button variant="ghost" size="sm" onClick={() => handleOpenConfig(lastOpenedConfig.id)}>
              Resume last opened
            </Button>
          ) : null}
        </header>
        <div className="space-y-4">
          <div className="rounded-xl border border-border">
            <div className="px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Active configuration</p>
            </div>
            <Separator />
            {activeConfiguration ? (
              <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,2fr),auto] md:items-center hover:bg-background">
                <button
                  type="button"
                  className="cursor-pointer space-y-1 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  onClick={() => handleOpenConfig(activeConfiguration.id)}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-foreground">{activeConfiguration.display_name}</h2>
                    <StatusPill status={activeConfiguration.status} />
                    <span className="text-xs text-muted-foreground">Used for extraction runs</span>
                  </div>
                  <p className="text-sm text-muted-foreground">Updated {formatTimestamp(activeConfiguration.updated_at)}</p>
                </button>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button
                    size="sm"
                    onClick={(event) => {
                      event.stopPropagation();
                      openDuplicateDialog(activeConfiguration);
                    }}
                  >
                    Duplicate to edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={(event) => openContextMenu(event, activeConfiguration.id)}>
                    ⋯
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2 p-4">
                <p className="text-sm font-semibold text-foreground">No active configuration</p>
                <p className="text-sm text-muted-foreground">
                  Extraction runs will be blocked until you make a draft configuration active.
                </p>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-border">
            <div className="flex items-center justify-between px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Drafts ({draftConfigurations.length})</p>
              {draftConfigurations.length === 0 && activeConfiguration ? (
                <p className="text-xs text-muted-foreground">Duplicate Active to start editing.</p>
              ) : null}
            </div>
            <Separator />
            {draftConfigurations.length ? (
              <div className="flex flex-col">
                {draftConfigurations.map((config, index) => (
                  <Fragment key={config.id}>
                    <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,2fr),auto] md:items-center hover:bg-background">
                      <button
                        type="button"
                        className="cursor-pointer space-y-1 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                        onClick={() => handleOpenConfig(config.id)}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-semibold text-foreground">{config.display_name}</h3>
                          <StatusPill status={config.status} />
                          {lastOpenedConfig?.id === config.id ? (
                            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                              Last opened
                            </span>
                          ) : null}
                        </div>
                        <p className="text-sm text-muted-foreground">Updated {formatTimestamp(config.updated_at)}</p>
                      </button>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleOpenMakeActiveDialog(config);
                          }}
                        >
                          Make active
                        </Button>
                        <Button size="sm" variant="ghost" onClick={(event) => openContextMenu(event, config.id)}>
                          ⋯
                        </Button>
                      </div>
                    </div>
                    {index < draftConfigurations.length - 1 ? <Separator /> : null}
                  </Fragment>
                ))}
              </div>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">No draft configurations.</div>
            )}
          </div>

          <div className="rounded-xl border border-border">
            <div className="px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Archived ({archivedConfigurations.length})
              </p>
            </div>
            <Separator />
            {archivedConfigurations.length ? (
              <div className="flex flex-col">
                {archivedConfigurations.map((config, index) => (
                  <Fragment key={config.id}>
                    <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,2fr),auto] md:items-center hover:bg-background">
                      <button
                        type="button"
                        className="cursor-pointer space-y-1 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                        onClick={() => handleOpenConfig(config.id)}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-semibold text-foreground">{config.display_name}</h3>
                          <StatusPill status={config.status} />
                        </div>
                        <p className="text-sm text-muted-foreground">Updated {formatTimestamp(config.updated_at)}</p>
                      </button>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button
                          size="sm"
                          onClick={(event) => {
                            event.stopPropagation();
                            openDuplicateDialog(config);
                          }}
                        >
                          Duplicate to edit
                        </Button>
                        <Button size="sm" variant="ghost" onClick={(event) => openContextMenu(event, config.id)}>
                          ⋯
                        </Button>
                      </div>
                    </div>
                    {index < archivedConfigurations.length - 1 ? <Separator /> : null}
                  </Fragment>
                ))}
              </div>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">No archived configurations.</div>
            )}
          </div>
        </div>
      </section>

      <aside className="space-y-4 rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-foreground">New configuration</h2>
          <p className="text-sm text-muted-foreground">Copy the starter template to begin editing detectors, hooks, and manifests.</p>
        </div>
        <form onSubmit={handleCreate} className="space-y-4">
          <FormField label="Configuration name" required>
            <Input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Membership normalization"
              disabled={createConfig.isPending}
            />
          </FormField>
          {renderTemplateField(createConfig.isPending)}
          {creationError ? <p className="text-sm font-medium text-destructive">{creationError}</p> : null}
          <Button
            type="submit"
            className="w-full"
            disabled={!canSubmit || createConfig.isPending}
          >
            Create from template
          </Button>
        </form>
        <Separator />
        <div className="space-y-3">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Import configuration</h2>
            <p className="text-sm text-muted-foreground">Upload an ADE export (.zip) to create a new draft configuration.</p>
          </div>
          <form onSubmit={handleImport} className="space-y-4">
            <FormField label="Configuration name" required>
              <Input
                value={importDisplayName}
                onChange={(event) => setImportDisplayName(event.target.value)}
                placeholder="Imported configuration"
                disabled={importConfig.isPending}
              />
            </FormField>
            <FormField label="Archive (.zip)" required>
              <Input
                type="file"
                ref={importInputRef}
                accept=".zip"
                onChange={handleImportFileChange}
                disabled={importConfig.isPending}
              />
              {importFile ? (
                <p className="mt-1 text-xs text-muted-foreground" aria-live="polite">
                  {importFile.name}
                </p>
              ) : null}
            </FormField>
            {importError ? <p className="text-sm font-medium text-destructive">{importError}</p> : null}
            <Button
              type="submit"
              className="w-full"
              disabled={!canImport || importConfig.isPending}
            >
              Import archive
            </Button>
          </form>
        </div>
      </aside>

      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu ? { x: contextMenu.x, y: contextMenu.y } : null}
        onClose={() => setContextMenu(null)}
        items={contextMenuItems}
        appearance="light"
      />

      <ConfirmDialog
        open={Boolean(makeActiveTarget)}
        title={
          makeActiveDialogState?.stage === "checking"
            ? "Checking configuration…"
            : makeActiveDialogState?.stage === "issues"
              ? "Fix validation issues first"
              : "Make configuration active?"
        }
        description={
          makeActiveDialogState?.stage === "checking"
            ? "Running validation before activation."
            : makeActiveDialogState?.stage === "issues"
              ? "This configuration has validation issues and can’t be activated yet."
              : activeConfiguration && makeActiveTarget
                ? `This becomes the workspace’s live configuration for extraction runs. The current active configuration “${activeConfiguration.display_name}” will be archived.`
                : "This becomes the workspace’s live configuration for extraction runs."
        }
        confirmLabel={
          makeActiveDialogState?.stage === "issues"
            ? "Open editor"
            : makeActiveDialogState?.stage === "error"
              ? "Close"
              : "Make active"
        }
        cancelLabel="Cancel"
        onCancel={closeMakeActiveDialog}
        onConfirm={() => {
          if (!makeActiveTarget) {
            closeMakeActiveDialog();
            return;
          }
          if (makeActiveDialogState?.stage === "issues") {
            closeMakeActiveDialog();
            handleOpenEditor(makeActiveTarget.id);
            return;
          }
          if (makeActiveDialogState?.stage === "error") {
            closeMakeActiveDialog();
            return;
          }
          handleConfirmMakeActive();
        }}
        isConfirming={makeActiveConfig.isPending}
        confirmDisabled={makeActiveDialogState?.stage === "checking" || makeActiveConfig.isPending}
      >
        {makeActiveDialogState?.stage === "checking" ? (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary" aria-hidden="true" />
            <span>Validating…</span>
          </div>
        ) : makeActiveDialogState?.stage === "issues" ? (
          <div className="space-y-2">
            <p className="text-sm text-foreground">Issues:</p>
            <ul className="max-h-56 space-y-2 overflow-auto rounded-lg border border-border bg-background p-3 text-xs text-foreground">
              {makeActiveDialogState.issues.map((issue) => (
                <li key={`${issue.path}:${issue.message}`} className="space-y-1">
                  <p className="font-semibold">{issue.path}</p>
                  <p className="text-muted-foreground">{issue.message}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : makeActiveDialogState?.stage === "error" ? (
          <p className="text-sm font-medium text-destructive">{makeActiveDialogState.message}</p>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        title="Archive active configuration?"
        description="This will leave the workspace with no active configuration. Extraction runs will be blocked until you make a draft active."
        confirmLabel="Archive"
        cancelLabel="Cancel"
        tone="danger"
        onCancel={closeArchiveDialog}
        onConfirm={handleConfirmArchive}
        isConfirming={archiveConfig.isPending}
        confirmDisabled={archiveConfig.isPending}
      >
        {archiveConfig.error ? (
          <p className="text-sm font-medium text-destructive">
            {archiveConfig.error instanceof Error ? archiveConfig.error.message : "Unable to archive configuration."}
          </p>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(duplicateSource)}
        title="Duplicate configuration"
        description={duplicateSource ? `Create a new draft based on “${duplicateSource.display_name}”.` : undefined}
        confirmLabel="Create draft"
        cancelLabel="Cancel"
        onCancel={closeDuplicateDialog}
        onConfirm={handleConfirmDuplicate}
        isConfirming={duplicateConfig.isPending}
        confirmDisabled={duplicateConfig.isPending || duplicateName.trim().length === 0}
      >
        <FormField label="New configuration name" required>
          <Input
            value={duplicateName}
            onChange={(event) => setDuplicateName(event.target.value)}
            placeholder="Copy of My Config"
            disabled={duplicateConfig.isPending}
          />
        </FormField>
        {duplicateNameError ? <p className="text-sm font-medium text-destructive">{duplicateNameError}</p> : null}
      </ConfirmDialog>
    </div>
  );
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

 
