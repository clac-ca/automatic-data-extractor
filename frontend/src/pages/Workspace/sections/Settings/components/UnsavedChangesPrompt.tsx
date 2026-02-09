import { useEffect } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useBlocker } from "react-router-dom";

interface UnsavedChangesPromptProps {
  readonly when: boolean;
  readonly title?: string;
  readonly description?: string;
  readonly confirmLabel?: string;
  readonly cancelLabel?: string;
}

export function UnsavedChangesPrompt({
  when,
  title = "Discard unsaved changes?",
  description = "You have unsaved changes. If you leave now, your edits will be lost.",
  confirmLabel = "Leave without saving",
  cancelLabel = "Stay on page",
}: UnsavedChangesPromptProps) {
  const blocker = useBlocker(when);

  useEffect(() => {
    if (!when) {
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [when]);

  useEffect(() => {
    if (!when && blocker.state === "blocked") {
      blocker.reset();
    }
  }, [blocker, when]);

  const confirmNavigation = () => {
    if (blocker.state !== "blocked") {
      return;
    }
    blocker.proceed();
  };

  const cancelNavigation = () => {
    if (blocker.state !== "blocked") {
      return;
    }
    blocker.reset();
  };

  return (
    <ConfirmDialog
      open={when && blocker.state === "blocked"}
      title={title}
      description={description}
      confirmLabel={confirmLabel}
      cancelLabel={cancelLabel}
      tone="danger"
      onConfirm={confirmNavigation}
      onCancel={cancelNavigation}
    />
  );
}

UnsavedChangesPrompt.displayName = "UnsavedChangesPrompt";
