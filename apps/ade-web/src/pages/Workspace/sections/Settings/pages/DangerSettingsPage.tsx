import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useNavigate } from "@app/navigation/history";
import { deleteWorkspace } from "@api/workspaces/api";
import { workspacesKeys } from "@hooks/workspaces";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { Alert } from "@components/ui/alert";
import { ConfirmDialog } from "@components/ui/confirm-dialog";
import { FormField } from "@components/ui/form-field";
import { Button } from "@components/tablecn/ui/button";
import { Input } from "@components/tablecn/ui/input";
import { SettingsSection } from "../components/SettingsSection";

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
      <SettingsSection
        title="Delete workspace"
        description="Permanently remove this workspace and all associated data. This action cannot be undone."
        tone="danger"
        actions={
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={!canDelete || deleteWorkspaceMutation.isPending}
          >
            {deleteWorkspaceMutation.isPending ? "Deleting..." : "Delete workspace"}
          </Button>
        }
      >
        {!canDelete ? (
          <Alert tone="warning">You need additional permissions to delete this workspace.</Alert>
        ) : null}
        {feedback ? <Alert tone="danger">{feedback}</Alert> : null}
        <p className="text-sm text-warning-700">
          All workspace configurations, documents, runs, and history will be removed.
        </p>
      </SettingsSection>

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
