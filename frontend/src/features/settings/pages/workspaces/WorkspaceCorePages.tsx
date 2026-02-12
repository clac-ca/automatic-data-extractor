import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";
import type { WorkspaceProfile } from "@/types/workspaces";

import { normalizeSettingsError, useDeleteSettingsWorkspaceMutation, useUpdateSettingsWorkspaceMutation } from "../../data";
import { settingsPaths } from "../../routing/contracts";
import {
  SettingsAccessDenied,
  SettingsDetailLayout,
  SettingsDetailSection,
  SettingsStickyActionBar,
  useSettingsListState,
} from "../../shared";

function hasWorkspacePermission(workspace: WorkspaceProfile, permission: string) {
  return workspace.permissions.some((entry) => entry.toLowerCase() === permission.toLowerCase());
}

function workspaceBreadcrumbs(workspace: WorkspaceProfile, section: string) {
  return [
    { label: "Settings", href: settingsPaths.home },
    { label: "Workspaces", href: settingsPaths.workspaces.list },
    { label: workspace.name, href: settingsPaths.workspaces.general(workspace.id) },
    { label: section },
  ] as const;
}

const WORKSPACE_GENERAL_SECTIONS = [{ id: "workspace-identity", label: "Workspace identity" }] as const;
const WORKSPACE_PROCESSING_SECTIONS = [{ id: "processing-state", label: "Processing state" }] as const;
const WORKSPACE_DANGER_SECTIONS = [{ id: "delete-workspace", label: "Delete workspace", tone: "danger" as const }] as const;

export function WorkspaceGeneralPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const canManage = hasWorkspacePermission(workspace, "workspace.settings.manage");
  const updateMutation = useUpdateSettingsWorkspaceMutation(workspace.id);

  const [name, setName] = useState(workspace.name);
  const [slug, setSlug] = useState(workspace.slug);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const hasUnsavedChanges = name !== workspace.name || slug !== workspace.slug;

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved workspace identity changes.",
    shouldBypassNavigation: () => updateMutation.isPending,
  });

  return (
    <SettingsDetailLayout
      title="General"
      subtitle="Update workspace identity used across navigation and shared links."
      breadcrumbs={workspaceBreadcrumbs(workspace, "General")}
      actions={workspace.is_default ? <Badge variant="secondary">Default workspace</Badge> : null}
      sections={WORKSPACE_GENERAL_SECTIONS}
      defaultSectionId="workspace-identity"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      <SettingsDetailSection id="workspace-identity" title="Workspace identity">
        <FormField label="Workspace name" required>
          <Input value={name} onChange={(event) => setName(event.target.value)} disabled={!canManage || updateMutation.isPending} />
        </FormField>
        <FormField label="Workspace slug" required>
          <Input value={slug} onChange={(event) => setSlug(event.target.value)} disabled={!canManage || updateMutation.isPending} />
        </FormField>

        {!canManage ? (
          <Alert tone="info">You can view this workspace but cannot edit general settings.</Alert>
        ) : null}
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave={canManage}
        disabledReason={canManage ? undefined : "You do not have permission to update workspace details."}
        isSaving={updateMutation.isPending}
        onSave={() => {
          setErrorMessage(null);
          setSuccessMessage(null);
          void updateMutation
            .mutateAsync({ name: name.trim() || null, slug: slug.trim() || null })
            .then(() => setSuccessMessage("Workspace details updated."))
            .catch((error) => {
              setErrorMessage(normalizeSettingsError(error, "Unable to update workspace.").message);
            });
        }}
        onDiscard={() => {
          setName(workspace.name);
          setSlug(workspace.slug);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Workspace detail changes are pending"
      />
    </SettingsDetailLayout>
  );
}

export function WorkspaceProcessingPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const canManage = hasWorkspacePermission(workspace, "workspace.settings.manage");
  const updateMutation = useUpdateSettingsWorkspaceMutation(workspace.id);

  const [isPaused, setIsPaused] = useState(workspace.processing_paused ?? false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const hasUnsavedChanges = isPaused !== (workspace.processing_paused ?? false);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved processing changes.",
    shouldBypassNavigation: () => updateMutation.isPending,
  });

  if (!canManage) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
  }

  return (
    <SettingsDetailLayout
      title="Processing"
      subtitle="Pause or resume automatic processing for this workspace."
      breadcrumbs={workspaceBreadcrumbs(workspace, "Processing")}
      sections={WORKSPACE_PROCESSING_SECTIONS}
      defaultSectionId="processing-state"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      <SettingsDetailSection id="processing-state" title="Processing state">
        <Alert tone={isPaused ? "warning" : "info"}>
          {isPaused
            ? "Processing is paused. Uploads are accepted but runs will not start."
            : "Processing is active. Uploaded files can start runs automatically."}
        </Alert>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isPaused} onChange={(event) => setIsPaused(event.target.checked)} disabled={updateMutation.isPending} />
          Pause processing
        </label>
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave
        isSaving={updateMutation.isPending}
        onSave={() => {
          setErrorMessage(null);
          setSuccessMessage(null);
          void updateMutation
            .mutateAsync({ processing_paused: isPaused })
            .then(() => setSuccessMessage(isPaused ? "Processing paused." : "Processing resumed."))
            .catch((error) => {
              setErrorMessage(normalizeSettingsError(error, "Unable to update processing state.").message);
            });
        }}
        onDiscard={() => {
          setIsPaused(workspace.processing_paused ?? false);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Processing changes are pending"
      />
    </SettingsDetailLayout>
  );
}

export function WorkspaceDangerPage({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const navigate = useNavigate();
  const listState = useSettingsListState();
  const canDelete =
    hasWorkspacePermission(workspace, "workspace.delete") ||
    hasWorkspacePermission(workspace, "workspace.settings.manage");
  const deleteMutation = useDeleteSettingsWorkspaceMutation(workspace.id);

  const [confirmationText, setConfirmationText] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const confirmationMatches = useMemo(() => {
    const value = confirmationText.trim().toLowerCase();
    return value === workspace.slug.toLowerCase() || value === workspace.name.toLowerCase();
  }, [confirmationText, workspace.name, workspace.slug]);

  if (!canDelete) {
    return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
  }

  return (
    <SettingsDetailLayout
      title="Danger"
      subtitle="Delete this workspace and all associated data. This action cannot be undone."
      breadcrumbs={workspaceBreadcrumbs(workspace, "Danger")}
      sections={WORKSPACE_DANGER_SECTIONS}
      defaultSectionId="delete-workspace"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}

      <SettingsDetailSection
        id="delete-workspace"
        title="Delete workspace"
        tone="danger"
        description="Deleting a workspace removes configurations, documents, runs, and audit history."
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">Type the workspace slug to confirm permanent deletion.</p>
          <Button variant="destructive" onClick={() => setConfirmOpen(true)} disabled={deleteMutation.isPending}>
            {deleteMutation.isPending ? "Deleting..." : "Delete workspace"}
          </Button>
        </div>
      </SettingsDetailSection>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete workspace?"
        description={`Type ${workspace.slug} to confirm deletion.`}
        confirmLabel="Delete workspace"
        tone="danger"
        confirmDisabled={!confirmationMatches}
        isConfirming={deleteMutation.isPending}
        onCancel={() => {
          setConfirmOpen(false);
          setConfirmationText("");
          setErrorMessage(null);
        }}
        onConfirm={async () => {
          setErrorMessage(null);
          try {
            await deleteMutation.mutateAsync();
            navigate(listState.withCurrentSearch(settingsPaths.workspaces.list), { replace: true });
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to delete workspace.").message);
          }
        }}
      >
        <FormField label="Workspace slug" required>
          <Input value={confirmationText} onChange={(event) => setConfirmationText(event.target.value)} placeholder={workspace.slug} disabled={deleteMutation.isPending} />
        </FormField>
      </ConfirmDialog>
    </SettingsDetailLayout>
  );
}
