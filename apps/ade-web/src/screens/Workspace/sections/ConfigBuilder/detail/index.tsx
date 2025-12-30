import { useCallback, useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { ConfirmDialog } from "@ui/ConfirmDialog";
import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";

import {
  exportConfiguration,
  useArchiveConfigurationMutation,
  useConfigurationQuery,
  useConfigurationsQuery,
  useDuplicateConfigurationMutation,
  useMakeActiveConfigurationMutation,
  validateConfiguration,
} from "@shared/configurations";
import { useNotifications } from "@shared/notifications";
import { createLastSelectionStorage, persistLastSelection } from "../storage";
import { StatusPill } from "../components/StatusPill";
import { normalizeConfigStatus, suggestDuplicateName } from "../utils/configs";

interface WorkspaceConfigRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function WorkspaceConfigRoute({ params }: WorkspaceConfigRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const { notifyToast } = useNotifications();
  const configId = params?.configId;
  const lastSelectionStorage = useMemo(() => createLastSelectionStorage(workspace.id), [workspace.id]);

  const configQuery = useConfigurationQuery({ workspaceId: workspace.id, configurationId: configId });
  const { refetch: refetchConfig } = configQuery;
  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const { refetch: refetchConfigurations } = configurationsQuery;
  const config = configQuery.data;
  const configurationId = config?.id ?? configId ?? "";
  const status = normalizeConfigStatus(config?.status);
  const isDraft = status === "draft";

  useEffect(() => {
    if (!configId || !config) {
      return;
    }
    persistLastSelection(lastSelectionStorage, configId);
  }, [configId, config, lastSelectionStorage]);

  const detailPath = configurationId
    ? `/workspaces/${workspace.id}/config-builder/${encodeURIComponent(configurationId)}`
    : "";
  const openEditor = useCallback(() => {
    if (!detailPath) {
      return;
    }
    navigate(`${detailPath}/editor`);
  }, [detailPath, navigate]);

  const activeConfiguration = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    for (const item of items) {
      if (normalizeConfigStatus(item.status) === "active") {
        return item;
      }
    }
    return null;
  }, [configurationsQuery.data?.items]);

  const existingNames = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    return new Set(items.map((c) => c.display_name.trim().toLowerCase()));
  }, [configurationsQuery.data?.items]);

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const openContextMenu = useCallback((event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    setContextMenu({ x: rect.right + 8, y: rect.bottom });
  }, []);

  const [exporting, setExporting] = useState(false);
  const handleExport = useCallback(async () => {
    if (!config) {
      return;
    }
    setExporting(true);
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
      setExporting(false);
    }
  }, [config, notifyToast, workspace.id]);

  const makeActiveConfig = useMakeActiveConfigurationMutation(workspace.id);
  const archiveConfig = useArchiveConfigurationMutation(workspace.id);
  const duplicateConfig = useDuplicateConfigurationMutation(workspace.id);

  type MakeActiveDialogState =
    | { stage: "checking" }
    | { stage: "confirm" }
    | { stage: "issues"; issues: readonly { path: string; message: string }[] }
    | { stage: "error"; message: string };

  const [makeActiveOpen, setMakeActiveOpen] = useState(false);
  const [makeActiveState, setMakeActiveState] = useState<MakeActiveDialogState | null>(null);

  useEffect(() => {
    if (!makeActiveOpen || !config || !isDraft) {
      return;
    }
    let cancelled = false;
    setMakeActiveState({ stage: "checking" });
    void validateConfiguration(workspace.id, config.id)
      .then((result) => {
        if (cancelled) return;
        if (Array.isArray(result.issues) && result.issues.length > 0) {
          setMakeActiveState({ stage: "issues", issues: result.issues });
          return;
        }
        setMakeActiveState({ stage: "confirm" });
      })
      .catch((error) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Unable to validate configuration.";
        setMakeActiveState({ stage: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [config, isDraft, makeActiveOpen, workspace.id]);

  const openMakeActiveDialog = useCallback(() => {
    makeActiveConfig.reset();
    setMakeActiveState({ stage: "checking" });
    setMakeActiveOpen(true);
  }, [makeActiveConfig]);

  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState("");
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const openDuplicateDialog = useCallback(() => {
    if (!config) {
      return;
    }
    duplicateConfig.reset();
    setDuplicateError(null);
    setDuplicateName(suggestDuplicateName(config.display_name, existingNames));
    setDuplicateOpen(true);
  }, [config, duplicateConfig, existingNames]);

  const [archiveOpen, setArchiveOpen] = useState(false);
  const openArchiveDialog = useCallback(() => {
    archiveConfig.reset();
    setArchiveOpen(true);
  }, [archiveConfig]);

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    const items: ContextMenuItem[] = [
      {
        id: "export",
        label: exporting ? "Exporting…" : "Export",
        onSelect: () => void handleExport(),
        disabled: exporting,
      },
      {
        id: "duplicate",
        label: "Duplicate to edit",
        onSelect: openDuplicateDialog,
        dividerAbove: true,
      },
    ];
    if (status === "active") {
      items.push({
        id: "archive",
        label: "Archive",
        onSelect: openArchiveDialog,
        danger: true,
        dividerAbove: true,
      });
    }
    return items;
  }, [exporting, handleExport, openArchiveDialog, openDuplicateDialog, status]);

  const handleConfirmDuplicate = useCallback(() => {
    if (!config) {
      return;
    }
    const trimmed = duplicateName.trim();
    if (!trimmed) {
      setDuplicateError("Enter a name for the new draft configuration.");
      return;
    }
    setDuplicateError(null);
    duplicateConfig.mutate(
      { sourceConfigurationId: config.id, displayName: trimmed },
      {
        onSuccess(record) {
          notifyToast({ title: "Draft created.", intent: "success", duration: 3500 });
          setDuplicateOpen(false);
          navigate(`/workspaces/${workspace.id}/config-builder/${encodeURIComponent(record.id)}/editor`);
        },
        onError(error) {
          setDuplicateError(error instanceof Error ? error.message : "Unable to duplicate configuration.");
        },
      },
    );
  }, [config, duplicateConfig, duplicateName, navigate, notifyToast, workspace.id]);

  const handleConfirmMakeActive = useCallback(() => {
    if (!config) {
      return;
    }
    makeActiveConfig.mutate(
      { configurationId: config.id },
      {
        onSuccess() {
          notifyToast({ title: "Configuration is now active.", intent: "success", duration: 4000 });
          setMakeActiveOpen(false);
          setMakeActiveState(null);
          void refetchConfigurations();
          void refetchConfig();
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
  }, [config, makeActiveConfig, notifyToast, refetchConfig, refetchConfigurations]);

  const handleConfirmArchive = useCallback(() => {
    if (!config) {
      return;
    }
    archiveConfig.mutate(
      { configurationId: config.id },
      {
        onSuccess() {
          notifyToast({ title: "Active configuration archived.", intent: "success", duration: 4000 });
          setArchiveOpen(false);
          void refetchConfigurations();
          void refetchConfig();
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
  }, [archiveConfig, config, notifyToast, refetchConfig, refetchConfigurations]);

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="Pick a configuration from the list to view its details."
      />
    );
  }

  if (configQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration"
        description="Fetching configuration details."
      />
    );
  }

  if (configQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration"
        description="Try refreshing the page."
      />
    );
  }

  if (!config) {
    return (
      <PageState
        variant="error"
        title="Configuration unavailable"
        description="The selected configuration could not be found. It may have been deleted."
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <section className="space-y-3 rounded-2xl border border-border bg-card p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Configuration</p>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">{config.display_name}</h1>
              <StatusPill status={config.status} />
            </div>
          </div>
            <div className="flex flex-wrap items-center gap-2">
            {isDraft ? (
              <Button variant="secondary" onClick={openMakeActiveDialog}>
                Make active
              </Button>
            ) : (
              <Button onClick={openDuplicateDialog}>Duplicate to edit</Button>
            )}
            <Button variant="ghost" onClick={openEditor}>
              Open editor
            </Button>
            <Button variant="ghost" size="sm" onClick={openContextMenu} aria-label="More actions">
              ⋯
            </Button>
          </div>
        </header>

        {!isDraft ? (
          <div className="rounded-lg border border-border bg-background p-4">
            <p className="text-sm font-semibold text-foreground">Read-only configuration</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Active and archived configurations can’t be edited. Duplicate this configuration to create a draft you can change.
            </p>
            <div className="mt-3">
              <Button size="sm" onClick={openDuplicateDialog}>
                Duplicate to edit
              </Button>
            </div>
          </div>
        ) : null}

        <dl className="grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Config ID</dt>
            <dd className="text-sm text-foreground">{config.id}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
            <dd className="text-sm text-foreground">{normalizeConfigStatus(config.status)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Updated</dt>
            <dd className="text-sm text-foreground">{formatTimestamp(config.updated_at)}</dd>
          </div>
          {config.activated_at ? (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Activated</dt>
              <dd className="text-sm text-foreground">{formatTimestamp(config.activated_at)}</dd>
            </div>
          ) : null}
        </dl>
      </section>
      <section className="flex-1 rounded-2xl border border-dashed border-border-strong bg-background p-6">
        <h2 className="text-base font-semibold text-foreground">Overview</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          The refreshed config workbench will eventually surface manifest summaries, validation history, and deployment metrics
          here. For now this page offers a quick launch point into the editor while we rebuild the experience.
        </p>
      </section>

      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu}
        onClose={() => setContextMenu(null)}
        items={contextMenuItems}
        appearance="light"
      />

      <ConfirmDialog
        open={makeActiveOpen}
        title={
          makeActiveState?.stage === "checking"
            ? "Checking configuration…"
            : makeActiveState?.stage === "issues"
              ? "Fix validation issues first"
              : "Make configuration active?"
        }
        description={
          makeActiveState?.stage === "checking"
            ? "Running validation before activation."
            : makeActiveState?.stage === "issues"
              ? "This configuration has validation issues and can’t be activated yet."
              : activeConfiguration
                ? `This becomes the workspace’s live configuration for extraction runs. The current active configuration “${activeConfiguration.display_name}” will be archived.`
                : "This becomes the workspace’s live configuration for extraction runs."
        }
        confirmLabel={
          makeActiveState?.stage === "issues"
            ? "Open editor"
            : makeActiveState?.stage === "error"
              ? "Close"
              : "Make active"
        }
        cancelLabel="Cancel"
        onCancel={() => {
          setMakeActiveOpen(false);
          setMakeActiveState(null);
        }}
        onConfirm={() => {
          if (makeActiveState?.stage === "issues") {
            setMakeActiveOpen(false);
            openEditor();
            return;
          }
          if (makeActiveState?.stage === "error") {
            setMakeActiveOpen(false);
            setMakeActiveState(null);
            return;
          }
          handleConfirmMakeActive();
        }}
        isConfirming={makeActiveConfig.isPending}
        confirmDisabled={makeActiveState?.stage === "checking" || makeActiveConfig.isPending}
      >
        {makeActiveState?.stage === "checking" ? (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-brand-600" aria-hidden="true" />
            <span>Validating…</span>
          </div>
        ) : makeActiveState?.stage === "issues" ? (
          <div className="space-y-2">
            <p className="text-sm text-foreground">Issues:</p>
            <ul className="max-h-56 space-y-2 overflow-auto rounded-lg border border-border bg-background p-3 text-xs text-foreground">
              {makeActiveState.issues.map((issue) => (
                <li key={`${issue.path}:${issue.message}`} className="space-y-1">
                  <p className="font-semibold">{issue.path}</p>
                  <p className="text-muted-foreground">{issue.message}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : makeActiveState?.stage === "error" ? (
          <p className="text-sm font-medium text-danger-600">{makeActiveState.message}</p>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={archiveOpen}
        title="Archive active configuration?"
        description="This will leave the workspace with no active configuration. Extraction runs will be blocked until you make a draft active."
        confirmLabel="Archive"
        cancelLabel="Cancel"
        tone="danger"
        onCancel={() => setArchiveOpen(false)}
        onConfirm={handleConfirmArchive}
        isConfirming={archiveConfig.isPending}
        confirmDisabled={archiveConfig.isPending}
      >
        {archiveConfig.error ? (
          <p className="text-sm font-medium text-danger-600">
            {archiveConfig.error instanceof Error ? archiveConfig.error.message : "Unable to archive configuration."}
          </p>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={duplicateOpen}
        title="Duplicate configuration"
        description={`Create a new draft based on “${config.display_name}”.`}
        confirmLabel="Create draft"
        cancelLabel="Cancel"
        onCancel={() => setDuplicateOpen(false)}
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
        {duplicateError ? <p className="text-sm font-medium text-danger-600">{duplicateError}</p> : null}
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
