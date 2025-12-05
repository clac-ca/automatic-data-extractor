import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useNavigate } from "@app/nav/history";
import { deleteWorkspace, workspacesKeys } from "@features/Workspace/api/workspaces-api";
import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { ConfirmDialog } from "../components/ConfirmDialog";
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

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-slate-900">Delete workspace</h3>
            <p className="text-sm text-slate-600">
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
        <p className="mt-3 text-sm text-amber-700">
          All workspace configurations, documents, runs, and history will be removed.
        </p>
      </div>

      <div className="rounded-2xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-800">
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
        <p className="text-xs text-slate-500">
            Enter <strong>{workspace.slug}</strong> to confirm deletion.
          </p>
      </ConfirmDialog>
    </div>
  );
}
