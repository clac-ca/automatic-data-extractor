import { useState } from "react";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useUpdateWorkspaceMutation } from "../hooks/useUpdateWorkspaceMutation";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SettingsSection } from "../components/SettingsSection";

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
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <SettingsSection
        title="Processing queue"
        description={
          isPaused
            ? "Uploads are stored, but runs will not start until processing is resumed."
            : "Runs start automatically after upload when an active configuration is available."
        }
        actions={
          <Button
            type="button"
            variant={isPaused ? "default" : "secondary"}
            size="sm"
            onClick={handleToggle}
            disabled={!canManage || updateWorkspace.isPending}
          >
            {updateWorkspace.isPending
              ? "Updating..."
              : isPaused
                ? "Resume processing"
                : "Pause processing"}
          </Button>
        }
      >
        {!canManage ? (
          <Alert tone="warning">You need workspace settings permissions to update processing behavior.</Alert>
        ) : null}
        {isPaused ? (
          <div className="rounded-xl border border-border/60 bg-accent px-3 py-2 text-xs text-accent-foreground">
            Processing is paused. Pending documents will remain in a waiting state.
          </div>
        ) : null}
      </SettingsSection>
    </div>
  );
}
