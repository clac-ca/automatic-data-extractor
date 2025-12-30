import clsx from "clsx";
import { useEffect, useId, useRef, useState } from "react";

import { ChevronDownIcon, FolderOpenIcon, LockIcon } from "@ui/Icons";

import type { DocumentQueueReason, DocumentQueueState, DocumentStatus } from "../types";
import { STATUS_STYLES, resolveStatusLabel } from "./StatusPill";

const STATUS_ORDER: DocumentStatus[] = ["queued", "processing", "ready", "failed", "archived"];
const SYSTEM_STATUSES = new Set<DocumentStatus>(["queued", "processing", "ready", "failed"]);

export function StatusPicker({
  status,
  queueState,
  queueReason,
  disabled = false,
  onArchive,
  onRestore,
}: {
  status: DocumentStatus;
  queueState?: DocumentQueueState | null;
  queueReason?: DocumentQueueReason | null;
  disabled?: boolean;
  onArchive: () => void;
  onRestore: () => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const listId = useId();

  const isArchived = status === "archived";
  const canArchive = !disabled && !isArchived;
  const canRestore = !disabled && isArchived;

  useEffect(() => {
    if (!open) return;

    const onClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (containerRef.current && target && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const style = STATUS_STYLES[status];
  const label = resolveStatusLabel(status, queueState, queueReason);

  const handleArchive = () => {
    if (!canArchive) return;
    onArchive();
    setOpen(false);
  };

  const handleRestore = () => {
    if (!canRestore) return;
    onRestore();
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative" data-ignore-row-click="true">
      <button
        type="button"
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev);
        }}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={open ? listId : undefined}
        className={clsx(
          "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          style.pill,
          disabled ? "cursor-not-allowed opacity-60" : "hover:opacity-90",
        )}
      >
        <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
        <span className="min-w-0 truncate">{label}</span>
        <ChevronDownIcon
          className={clsx("h-3.5 w-3.5 text-current opacity-70 transition", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div
          className="absolute left-0 z-30 mt-2 w-64 rounded-2xl border border-border bg-card shadow-lg"
          role="listbox"
          id={listId}
          data-ignore-row-click="true"
        >
          <div className="border-b border-border px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Status
          </div>
          <div className="space-y-1 p-2">
            {STATUS_ORDER.map((value) => {
              const optionStyle = STATUS_STYLES[value];
              const isSelected = value === status;
              const isSystem = SYSTEM_STATUSES.has(value);
              const isArchiveOption = value === "archived";
              const isDisabled = disabled || isSystem || (isArchiveOption && !canArchive);
              return (
                <button
                  key={value}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  disabled={isDisabled}
                  onClick={isArchiveOption ? handleArchive : undefined}
                  className={clsx(
                    "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-xs font-semibold transition",
                    isSelected ? "bg-brand-50 text-foreground dark:bg-brand-500/20" : "hover:bg-background",
                    isDisabled && "cursor-not-allowed text-muted-foreground hover:bg-transparent",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span className={clsx("h-2.5 w-2.5 rounded-full", optionStyle.dot)} />
                    <span>{optionStyle.label}</span>
                  </span>
                  {isSystem ? (
                    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                      <LockIcon className="h-3 w-3" />
                      System
                    </span>
                  ) : isSelected ? (
                    <span className="text-[10px] text-muted-foreground">Current</span>
                  ) : null}
                </button>
              );
            })}
          </div>
          {canRestore ? (
            <div className="border-t border-border p-2">
              <button
                type="button"
                onClick={handleRestore}
                className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs font-semibold text-foreground transition hover:bg-background"
              >
                <FolderOpenIcon className="h-4 w-4 text-muted-foreground" />
                Restore to system status
              </button>
            </div>
          ) : null}
          <div className="border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
            System statuses update automatically.
          </div>
        </div>
      ) : null}
    </div>
  );
}
