import { useState } from "react";

import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { useUpdateWorkspaceMutation } from "@hooks/workspaces";
import { Alert } from "@components/Alert";
import { Button } from "@components/Button";
import { SettingsSectionHeader } from "../components/SettingsSectionHeader";

export function ProcessingSettingsPage() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const updateWorkspace = useUpdateWorkspaceMutation(workspace.id);
  const [feedback, setFeedback] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const canManage = hasPermission("workspace.settings.manage");
  const isPaused = workspace.processing_paused ?? false;

  const handleToggle = () => {
    if (!canManage || updateWorkspace.isPending) return;
    setFeedback(null);
    updateWorkspace.mutate(
      { processing_paused: !isPaused },
      {
        onSuccess: () => {
          setFeedback({
            tone: "success",
            message: isPaused ? "Processing resumed for this workspace." : "Processing paused for this workspace.",
          });
        },
        onError: (error) => {
          const message = error instanceof Error ? error.message : "Unable to update processing state.";
          setFeedback({ tone: "danger", message });
        },
      },
    );
  };

  return (
    <div className="space-y-6">
      <SettingsSectionHeader
        title="Processing"
        description="Pause or resume automatic document processing for this workspace."
      />

      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <div className="rounded-2xl border border-border bg-card p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-foreground">Processing queue</h3>
            <p className="text-sm text-muted-foreground">
              {isPaused
                ? "Uploads are stored, but runs will not start until processing is resumed."
                : "Runs start automatically after upload when an active configuration is available."}
            </p>
          </div>
          <Button
            type="button"
            variant={isPaused ? "primary" : "secondary"}
            onClick={handleToggle}
            disabled={!canManage || updateWorkspace.isPending}
            isLoading={updateWorkspace.isPending}
          >
            {isPaused ? "Resume processing" : "Pause processing"}
          </Button>
        </div>

        {!canManage ? (
          <Alert tone="warning" className="mt-3">
            You need workspace settings permissions to update processing behavior.
          </Alert>
        ) : null}
        {isPaused ? (
          <div className="mt-3 rounded-xl border border-warning-200 bg-warning-50 px-3 py-2 text-xs text-warning-800">
            Processing is paused. Pending documents will remain in a waiting state.
          </div>
        ) : null}
      </div>
    </div>
  );
}
