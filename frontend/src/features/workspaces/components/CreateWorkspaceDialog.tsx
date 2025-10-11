import { useEffect, useId, useRef } from "react";

import type { WorkspaceProfile } from "../../../shared/api/types";
import { CreateWorkspaceForm } from "./CreateWorkspaceForm";

interface CreateWorkspaceDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (workspace: WorkspaceProfile) => void;
}

export function CreateWorkspaceDialog({ open, onClose, onCreated }: CreateWorkspaceDialogProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const descriptionId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }

    const focusTarget =
      containerRef.current?.querySelector<HTMLElement>('[data-autofocus]') ??
      containerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
    focusTarget?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6">
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-workspace-title"
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="w-full max-w-lg rounded border border-slate-900 bg-slate-950 p-6 text-slate-100 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="create-workspace-title" className="text-xl font-semibold">
              Create workspace
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-slate-400">
              Name your workspace. Invite teammates from the Members tab after creation.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close create workspace dialog"
            className="rounded border border-transparent p-1 text-slate-400 transition hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <div className="mt-6">
          <CreateWorkspaceForm onCreated={onCreated} onCancel={onClose} autoFocus />
        </div>
      </div>
    </div>
  );
}
