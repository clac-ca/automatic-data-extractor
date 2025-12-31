import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useNavigate } from "@app/navigation/history";
import { deleteWorkspace } from "@api/workspaces/api";
import { workspacesKeys } from "@hooks/workspaces";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { Alert } from "@components/ui/alert";
import { Button } from "@components/ui/button";
import { ConfirmDialog } from "@components/ui/confirm-dialog";
import { FormField } from "@components/ui/form-field";
import { Input } from "@components/ui/input";
import { SettingsSectionHeader } from "../components/SettingsSectionHeader";

export function DangerSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmationInput, setConfirmationInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const deleteWorkspaceMutation = useMutation({
    mutationFn: () => deleteWorkspace(workspace.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workspacesKeys.all() });
      navigate("/workspaces", { replace: true });
    },
    onError: (error) => {
      setFeedback(error instanceof Error ? error.message : "Unable to delete workspace.");
    },
  });

  const canDelete = hasPermission("workspace.delete") || hasPermission("workspace.settings.manage");
  const confirmationMatch = useMemo(() => {
    const normalized = confirmationInput.trim().toLowerCase();
    return normalized.length > 0 && (normalized === workspace.slug.toLowerCase() || normalized === workspace.name.toLowerCase());
  }, [confirmationInput, workspace.name, workspace.slug]);

  return (
    <div className="space-y-6">
      <SettingsSectionHeader
        title="Danger zone"
        description="Delete this workspace when it is no longer needed."
      />

      <div className="rounded-2xl border border-border bg-card p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-foreground">Delete workspace</h3>
            <p className="text-sm text-muted-foreground">
              Permanently remove this workspace and all associated data. This action cannot be undone.
            </p>
          </div>
          <Button
            type="button"
            variant="danger"
            onClick={() => setConfirmOpen(true)}
            disabled={!canDelete || deleteWorkspaceMutation.isPending}
            isLoading={deleteWorkspaceMutation.isPending}
          >
            Delete workspace
          </Button>
        </div>

        {!canDelete ? (
          <Alert tone="warning" className="mt-3">
            You need additional permissions to delete this workspace.
          </Alert>
        ) : null}
        {feedback ? (
          <Alert tone="danger" className="mt-3">
            {feedback}
          </Alert>
        ) : null}
        <p className="mt-3 text-sm text-warning-700">
          All workspace configurations, documents, runs, and history will be removed.
        </p>
      </div>

      <div className="rounded-2xl border border-warning-100 bg-warning-50 p-4 text-sm text-warning-800">
        <p className="font-semibold">Looking for ADE safe mode?</p>
        <p className="mt-1">
          Safe mode is a system-wide control. Manage it from the system settings area instead of workspace settings.
        </p>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete this workspace?"
        description="Type the workspace slug to confirm. This cannot be undone."
        confirmLabel="Delete workspace"
        tone="danger"
        onCancel={() => {
          setConfirmOpen(false);
          setConfirmationInput("");
          setFeedback(null);
        }}
        onConfirm={() => {
          if (!confirmationMatch) {
            return;
          }
          setFeedback(null);
          deleteWorkspaceMutation.mutate();
        }}
        isConfirming={deleteWorkspaceMutation.isPending}
        confirmDisabled={!confirmationMatch}
      >
        <FormField label="Workspace slug" required>
          <Input
            value={confirmationInput}
            onChange={(event) => setConfirmationInput(event.target.value)}
            placeholder={workspace.slug}
            disabled={deleteWorkspaceMutation.isPending}
          />
        </FormField>
        <p className="text-xs text-muted-foreground">
            Enter <strong>{workspace.slug}</strong> to confirm deletion.
          </p>
      </ConfirmDialog>
    </div>
  );
}
