import clsx from "clsx";
import { createPortal } from "react-dom";
import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import type { RunStreamConnectionState } from "@/api/runs/api";

import type { WorkbenchConsoleStore } from "../state/consoleStore";
import type { WorkbenchConsoleLine } from "../types";
import { renderConsoleLine } from "./consoleFormatting";

export type PublishDialogPhase = "confirm" | "running" | "succeeded" | "failed";

interface PublishConfigurationDialogProps {
  readonly open: boolean;
  readonly phase: PublishDialogPhase;
  readonly isDirty: boolean;
  readonly canPublish: boolean;
  readonly isSubmitting?: boolean;
  readonly runId?: string | null;
  readonly activeConfigurationName?: string | null;
  readonly connectionState?: RunStreamConnectionState | null;
  readonly errorMessage?: string | null;
  readonly console: WorkbenchConsoleStore;
  readonly onCancel: () => void;
  readonly onStartPublish: () => void;
  readonly onDone: () => void;
  readonly onRetryPublish: () => void;
  readonly onDuplicateToEdit: () => void;
}

export function PublishConfigurationDialog({
  open,
  phase,
  isDirty,
  canPublish,
  isSubmitting = false,
  runId,
  activeConfigurationName,
  connectionState,
  errorMessage,
  console,
  onCancel,
  onStartPublish,
  onDone,
  onRetryPublish,
  onDuplicateToEdit,
}: PublishConfigurationDialogProps) {
  const canClose = phase !== "running";
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const retryButtonRef = useRef<HTMLButtonElement | null>(null);
  const doneButtonRef = useRef<HTMLButtonElement | null>(null);
  const logsRef = useRef<HTMLDivElement | null>(null);

  const snapshot = useSyncExternalStore(console.subscribe.bind(console), console.getSnapshot, console.getSnapshot);
  const lines = useMemo(() => {
    const entries: WorkbenchConsoleLine[] = [];
    for (let index = 0; index < snapshot.length; index += 1) {
      const line = console.getLine(index);
      if (line) {
        entries.push(line);
      }
    }
    return entries;
  }, [console, snapshot]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && canClose) {
        onCancel();
      }
      if (event.key !== "Tab") {
        return;
      }
      const root = dialogRef.current;
      if (!root) {
        return;
      }
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (focusable.length === 0) {
        return;
      }
      const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
      const nextIndex = event.shiftKey
        ? currentIndex <= 0
          ? focusable.length - 1
          : currentIndex - 1
        : currentIndex === focusable.length - 1
          ? 0
          : currentIndex + 1;
      focusable[nextIndex]?.focus();
      event.preventDefault();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canClose, onCancel, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    if (phase === "confirm") {
      confirmButtonRef.current?.focus();
      return;
    }
    if (phase === "failed") {
      retryButtonRef.current?.focus();
      return;
    }
    if (phase === "succeeded") {
      doneButtonRef.current?.focus();
    }
  }, [open, phase]);

  useEffect(() => {
    if (!open || lines.length === 0) {
      return;
    }
    const container = logsRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [lines.length, open, snapshot.version, phase]);

  if (!open) {
    return null;
  }

  const title =
    phase === "confirm"
      ? "Publish this draft configuration?"
      : phase === "running"
        ? "Publishing configuration"
        : phase === "succeeded"
          ? "Publish complete"
          : "Publish failed";
  const stateLabel =
    phase === "confirm"
      ? "Review"
      : phase === "running"
        ? "Running"
        : phase === "succeeded"
          ? "Success"
          : "Failure";
  const stateClass =
    phase === "succeeded"
      ? "bg-emerald-100 text-emerald-900"
      : phase === "failed"
        ? "bg-destructive/15 text-destructive"
        : phase === "running"
          ? "bg-accent text-accent-foreground"
          : "bg-muted text-foreground";

  return createPortal(
    <div className="fixed inset-0 z-[var(--app-z-modal)] px-4">
      <button
        type="button"
        className="absolute inset-0 bg-overlay"
        onClick={() => {
          if (canClose) {
            onCancel();
          }
        }}
        aria-label="Close publish dialog"
        disabled={!canClose}
      />
      <div className="relative flex min-h-full items-center justify-center">
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="publish-dialog-title"
          className="w-full max-w-4xl rounded-2xl border border-border bg-card p-6 shadow-2xl"
        >
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <div className={clsx("inline-flex rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.25em]", stateClass)}>
                {stateLabel}
              </div>
              <h2 id="publish-dialog-title" className="text-xl font-semibold text-foreground">
                {title}
              </h2>
              {phase === "confirm" ? (
                <p className="text-sm text-muted-foreground">
                  Publishing promotes this draft to active for your workspace.
                </p>
              ) : null}
            </div>
            {runId ? (
              <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                Run {runId}
              </div>
            ) : null}
          </div>

          {phase === "confirm" ? (
            <div className="space-y-3">
              <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                <p className="font-medium text-foreground">After publish:</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  <li>This configuration becomes active for newly uploaded documents by default.</li>
                  <li>This configuration becomes read-only. Duplicate it to continue editing.</li>
                  {activeConfigurationName ? (
                    <li>The current active configuration “{activeConfigurationName}” will be archived.</li>
                  ) : null}
                </ul>
              </div>
              {isDirty ? (
                <p className="rounded-md border border-accent/40 bg-accent/15 px-3 py-2 text-sm font-medium text-accent-foreground">
                  Unsaved changes will be saved before publish starts.
                </p>
              ) : null}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-muted/20 px-3 py-2">
                <p className="text-sm font-medium text-foreground" aria-live="polite">
                  {phase === "running"
                    ? "Streaming live publish logs."
                    : phase === "succeeded"
                      ? "Publish completed successfully."
                      : "Publish ended with an error."}
                </p>
                {phase === "running" || connectionState === "reconnecting" ? (
                  <span className="rounded border border-border bg-background px-2 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {formatConnectionState(connectionState)}
                  </span>
                ) : null}
              </div>
              {phase === "failed" && errorMessage ? (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive">
                  {errorMessage}
                </p>
              ) : null}
              <div
                ref={logsRef}
                className="h-72 overflow-auto rounded-md border border-border bg-card/40 p-3 font-mono text-[12px] leading-relaxed"
              >
                {lines.length === 0 ? (
                  <p className="text-muted-foreground">
                    {phase === "running" ? "Waiting for publish events…" : "No publish logs were captured."}
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {lines.map((line, index) => (
                      <li key={line.id ?? `${index}-${line.timestamp ?? ""}-${line.message}`}>
                        <div className="flex items-start gap-2">
                          <span className="min-w-[72px] pt-[2px] text-[10px] uppercase tracking-wide text-muted-foreground">
                            {formatTimestamp(line.timestamp)}
                          </span>
                          <span className={clsx("min-w-[58px] pt-[2px] text-[10px] uppercase tracking-wide", levelClass(line.level))}>
                            {line.level}
                          </span>
                          <span className="min-w-0 flex-1 break-words text-foreground">{renderConsoleLine(line)}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          <div className="mt-6 flex flex-wrap justify-end gap-2">
            {phase === "confirm" ? (
              <>
                <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
                  Keep editing draft
                </Button>
                <Button
                  ref={confirmButtonRef}
                  type="button"
                  onClick={onStartPublish}
                  disabled={!canPublish || isSubmitting}
                >
                  {isSubmitting ? "Publishing…" : "Publish configuration"}
                </Button>
              </>
            ) : null}
            {phase === "running" ? (
              <Button type="button" disabled>
                Publishing…
              </Button>
            ) : null}
            {phase === "succeeded" ? (
              <>
                <Button type="button" variant="ghost" onClick={onDuplicateToEdit}>
                  Duplicate to edit
                </Button>
                <Button ref={doneButtonRef} type="button" onClick={onDone}>
                  Done
                </Button>
              </>
            ) : null}
            {phase === "failed" ? (
              <>
                <Button type="button" variant="ghost" onClick={onCancel}>
                  Close
                </Button>
                <Button
                  ref={retryButtonRef}
                  type="button"
                  onClick={onRetryPublish}
                  disabled={!canPublish || isSubmitting}
                >
                  {isSubmitting ? "Retrying…" : "Retry publish"}
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function formatTimestamp(timestamp?: string): string {
  if (!timestamp) {
    return "--:--:--";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }
  return date.toLocaleTimeString([], { hour12: false });
}

function formatConnectionState(state?: RunStreamConnectionState | null): string {
  if (!state) {
    return "Connecting";
  }
  if (state === "streaming") {
    return "Streaming";
  }
  if (state === "reconnecting") {
    return "Reconnecting";
  }
  if (state === "failed") {
    return "Disconnected";
  }
  if (state === "completed") {
    return "Completed";
  }
  return "Connecting";
}

function levelClass(level: WorkbenchConsoleLine["level"]): string {
  if (level === "error") {
    return "text-destructive";
  }
  if (level === "warning") {
    return "text-amber-700";
  }
  if (level === "success") {
    return "text-emerald-700";
  }
  if (level === "debug") {
    return "text-muted-foreground";
  }
  return "text-sky-700";
}
