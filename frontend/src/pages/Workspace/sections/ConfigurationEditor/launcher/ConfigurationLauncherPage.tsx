import { useCallback, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useArchiveConfigurationMutation,
  useConfigurationsQuery,
  useCreateConfigurationMutation,
  useDuplicateConfigurationMutation,
  useImportConfigurationMutation,
} from "@/pages/Workspace/hooks/configurations";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useNotifications } from "@/providers/notifications";
import { buildConfigurationEditorPath } from "../paths";
import { normalizeConfigStatus, sortByUpdatedDesc, suggestDuplicateName } from "../utils/configs";
import { LauncherPrimaryActions } from "./components/LauncherPrimaryActions";
import { RecentConfigurationList, type LauncherConfigurationItem } from "./components/RecentConfigurationList";

function suggestAvailableName(baseName: string, existingNames: Set<string>): string {
  const base = baseName.trim() || "New configuration";
  if (!existingNames.has(base.toLowerCase())) {
    return base;
  }
  for (let index = 2; index < 100; index += 1) {
    const candidate = `${base} (${index})`;
    if (!existingNames.has(candidate.toLowerCase())) {
      return candidate;
    }
  }
  return `${base} (${Date.now()})`;
}

export function ConfigurationLauncherPage() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const { notifyToast } = useNotifications();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const createConfiguration = useCreateConfigurationMutation(workspace.id);
  const importConfiguration = useImportConfigurationMutation(workspace.id);
  const duplicateConfiguration = useDuplicateConfigurationMutation(workspace.id);
  const archiveConfiguration = useArchiveConfigurationMutation(workspace.id);

  const [archiveTargetId, setArchiveTargetId] = useState<string | null>(null);

  const configurations = configurationsQuery.data?.items ?? [];
  const configurationsById = useMemo(
    () => new Map(configurations.map((configuration) => [configuration.id, configuration])),
    [configurations],
  );
  const existingConfigNames = useMemo(
    () => new Set(configurations.map((configuration) => configuration.display_name.trim().toLowerCase())),
    [configurations],
  );
  const activeConfiguration = useMemo(
    () =>
      [...configurations]
        .filter((configuration) => normalizeConfigStatus(configuration.status) === "active")
        .sort((left, right) => sortByUpdatedDesc(left.updated_at, right.updated_at))[0] ?? null,
    [configurations],
  );

  const launcherItems = useMemo<LauncherConfigurationItem[]>(() => {
    const sorted = [...configurations].sort((left, right) => {
      const leftStatus = normalizeConfigStatus(left.status);
      const rightStatus = normalizeConfigStatus(right.status);
      if (leftStatus === "active" && rightStatus !== "active") {
        return -1;
      }
      if (rightStatus === "active" && leftStatus !== "active") {
        return 1;
      }
      return sortByUpdatedDesc(left.updated_at, right.updated_at);
    });

    return sorted.map((item) => ({
      id: item.id,
      displayName: item.display_name,
      status: item.status,
      updatedAt: item.updated_at,
      isActive: normalizeConfigStatus(item.status) === "active",
    }));
  }, [configurations]);

  const navigateToConfiguration = useCallback(
    (configurationId: string) => {
      const targetConfiguration = configurationsById.get(configurationId);
      if (!targetConfiguration) {
        return;
      }
      navigate(buildConfigurationEditorPath(workspace.id, configurationId));
    },
    [configurationsById, navigate, workspace.id],
  );

  const handleCreateDraft = useCallback(() => {
    const displayName = suggestAvailableName(`${workspace.name.trim() || "Workspace"} Config`, existingConfigNames);
    createConfiguration.mutate(
      {
        displayName,
        source: { type: "template" },
      },
      {
        onSuccess(record) {
          navigate(buildConfigurationEditorPath(workspace.id, record.id));
        },
        onError(error) {
          notifyToast({
            title: error instanceof Error ? error.message : "Unable to create configuration.",
            intent: "danger",
            duration: 5000,
          });
        },
      },
    );
  }, [
    createConfiguration,
    existingConfigNames,
    navigate,
    notifyToast,
    workspace.id,
    workspace.name,
  ]);

  const handleImportInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      event.target.value = "";
      if (!file) {
        return;
      }
      const displayName = suggestAvailableName("Imported configuration", existingConfigNames);
      importConfiguration.mutate(
        { displayName, file },
        {
          onSuccess(record) {
            navigate(buildConfigurationEditorPath(workspace.id, record.id));
          },
          onError(error) {
            notifyToast({
              title: error instanceof Error ? error.message : "Unable to import configuration.",
              intent: "danger",
              duration: 5000,
            });
          },
        },
      );
    },
    [existingConfigNames, importConfiguration, navigate, notifyToast, workspace.id],
  );

  const handleSaveAsNewDraft = useCallback(
    (configurationId: string) => {
      const source = configurationsById.get(configurationId);
      if (!source) {
        return;
      }
      const displayName = suggestDuplicateName(source.display_name, existingConfigNames);
      duplicateConfiguration.mutate(
        { sourceConfigurationId: source.id, displayName },
        {
          onSuccess(record) {
            notifyToast({
              title: `Draft created from ${source.display_name}.`,
              intent: "success",
              duration: 3500,
            });
            navigate(buildConfigurationEditorPath(workspace.id, record.id));
          },
          onError(error) {
            notifyToast({
              title: error instanceof Error ? error.message : "Unable to create draft.",
              intent: "danger",
              duration: 5000,
            });
          },
        },
      );
    },
    [
      configurationsById,
      duplicateConfiguration,
      existingConfigNames,
      navigate,
      notifyToast,
      workspace.id,
    ],
  );

  const handleConfirmArchiveDraft = useCallback(() => {
    if (!archiveTargetId) {
      return;
    }
    archiveConfiguration.mutate(
      { configurationId: archiveTargetId },
      {
        onSuccess() {
          setArchiveTargetId(null);
          notifyToast({ title: "Draft archived.", intent: "success", duration: 3000 });
        },
        onError(error) {
          notifyToast({
            title: error instanceof Error ? error.message : "Unable to archive draft.",
            intent: "danger",
            duration: 5000,
          });
        },
      },
    );
  }, [archiveConfiguration, archiveTargetId, notifyToast]);

  return (
    <div className="mx-auto flex h-full w-full max-w-7xl flex-col gap-6 p-6">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Configuration editor
        </p>
        <h1 className="text-2xl font-semibold text-foreground">Welcome</h1>
        <p className="text-sm text-muted-foreground">
          Pick a configuration to open, or start a new draft.
        </p>
      </div>

      <div className="grid min-h-0 gap-6 lg:grid-cols-[minmax(20rem,24rem)_1fr]">
        <LauncherPrimaryActions
          workspaceName={workspace.name}
          activeConfigurationName={activeConfiguration?.display_name ?? null}
          isCreatingDraft={createConfiguration.isPending}
          isImporting={importConfiguration.isPending}
          onCreateDraft={handleCreateDraft}
          onImportConfiguration={() => fileInputRef.current?.click()}
          onOpenActiveConfiguration={() => {
            if (!activeConfiguration) {
              return;
            }
            navigateToConfiguration(activeConfiguration.id);
          }}
        />

        <RecentConfigurationList
          items={launcherItems}
          isLoading={configurationsQuery.isLoading && !configurationsQuery.data}
          isError={configurationsQuery.isError}
          errorMessage={
            configurationsQuery.error instanceof Error
              ? configurationsQuery.error.message
              : "Unable to load configurations."
          }
          onRetry={() => {
            void configurationsQuery.refetch();
          }}
          onOpenConfiguration={navigateToConfiguration}
          onSaveAsNewDraft={handleSaveAsNewDraft}
          onArchiveDraft={setArchiveTargetId}
          isArchivingDraft={archiveConfiguration.isPending}
        />
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".zip"
        className="hidden"
        onChange={handleImportInputChange}
      />

      <ConfirmDialog
        open={Boolean(archiveTargetId)}
        title="Archive this draft?"
        description="Archiving removes it from draft editing flow but keeps history and run references."
        confirmLabel="Archive draft"
        cancelLabel="Cancel"
        tone="danger"
        onCancel={() => setArchiveTargetId(null)}
        onConfirm={handleConfirmArchiveDraft}
        isConfirming={archiveConfiguration.isPending}
      />
    </div>
  );
}
