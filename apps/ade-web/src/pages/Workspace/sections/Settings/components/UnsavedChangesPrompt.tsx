import { useEffect, useRef, useState } from "react";

import { ConfirmDialog } from "@components/ui/confirm-dialog";
import { useNavigate, useNavigationBlocker, type NavigationIntent } from "@app/navigation/history";

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
  const navigate = useNavigate();
  const [pendingIntent, setPendingIntent] = useState<NavigationIntent | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const allowNextNavigationRef = useRef(false);

  useEffect(() => {
    if (!when) {
      setDialogOpen(false);
      setPendingIntent(null);
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [when]);

  useNavigationBlocker(
    (intent) => {
      if (!when) {
        return true;
      }
      if (allowNextNavigationRef.current) {
        allowNextNavigationRef.current = false;
        return true;
      }
      setPendingIntent(intent);
      setDialogOpen(true);
      return false;
    },
    when,
  );

  const confirmNavigation = () => {
    if (!pendingIntent) {
      return;
    }
    allowNextNavigationRef.current = true;
    const replace = pendingIntent.kind === "replace" || pendingIntent.kind === "pop";
    navigate(pendingIntent.to, { replace });
    setDialogOpen(false);
    setPendingIntent(null);
    setTimeout(() => {
      allowNextNavigationRef.current = false;
    }, 0);
  };

  const cancelNavigation = () => {
    setDialogOpen(false);
    setPendingIntent(null);
  };

  return (
    <ConfirmDialog
      open={dialogOpen && when}
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
