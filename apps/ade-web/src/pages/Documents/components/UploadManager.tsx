import clsx from "clsx";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { DocumentUploadResponse } from "@api/documents";
import type { UploadManagerItem, UploadManagerSummary } from "@hooks/documents/uploadManager";
import { CloseIcon, RefreshIcon, UploadIcon } from "@components/Icons";

import { formatBytes } from "../utils";
import { UploadProgress } from "./UploadProgress";

type UploadItem = UploadManagerItem<DocumentUploadResponse>;

export function UploadManager({
  items,
  summary,
  onPause,
  onResume,
  onRetry,
  onCancel,
  onRemove,
  onClearCompleted,
}: {
  items: UploadItem[];
  summary: UploadManagerSummary;
  onPause: (uploadId: string) => void;
  onResume: (uploadId: string) => void;
  onRetry: (uploadId: string) => void;
  onCancel: (uploadId: string) => void;
  onRemove: (uploadId: string) => void;
  onClearCompleted: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const hasUploads = summary.totalCount > 0;
  const completedCount = summary.completedCount;

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (!open) return;
      const target = event.target as Node | null;
      if (containerRef.current && target && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const summaryLabel = useMemo(() => {
    if (!hasUploads) return "Uploads";
    const active = summary.uploadingCount + summary.queuedCount + summary.pausedCount;
    return active > 0 ? `${active} in progress` : `${summary.succeededCount} completed`;
  }, [hasUploads, summary]);

  if (!hasUploads) {
    return null;
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={clsx(
          "inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold shadow-sm transition",
          open ? "text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <UploadIcon className="h-4 w-4" />
        {summaryLabel}
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {summary.totalCount}
        </span>
      </button>

      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-[22rem] rounded-2xl border border-border bg-card p-4 shadow-lg">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Upload manager</p>
              <p className="text-[11px] text-muted-foreground">
                {summary.uploadingCount > 0 ? `${summary.uploadingCount} uploading` : "All uploads paused or complete"}
              </p>
            </div>
            {completedCount > 0 ? (
              <button
                type="button"
                onClick={() => onClearCompleted()}
                className="text-[11px] font-semibold text-brand-600 hover:text-brand-700"
              >
                Clear completed
              </button>
            ) : null}
          </div>

          <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>
              {summary.uploadedBytes > 0 ? formatBytes(summary.uploadedBytes) : "0 B"} /{" "}
              {summary.totalBytes > 0 ? formatBytes(summary.totalBytes) : "0 B"}
            </span>
            <span className="tabular-nums">{summary.percent}%</span>
          </div>
          <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
            <div
              className="h-1.5 rounded-full bg-brand-500"
              style={{ width: `${Math.max(0, Math.min(100, summary.percent))}%` }}
            />
          </div>

          <div className="mt-4 max-h-[18rem] space-y-3 overflow-y-auto pr-1">
            {items.map((item) => (
              <div key={item.id} className="rounded-xl border border-border bg-background px-3 py-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-foreground">{item.file.name}</p>
                    <p className="text-[10px] text-muted-foreground">{formatBytes(item.file.size)}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    {item.status === "uploading" ? (
                      <ActionButton label="Pause" onClick={() => onPause(item.id)}>
                        Pause
                      </ActionButton>
                    ) : null}
                    {item.status === "paused" ? (
                      <ActionButton label="Resume" onClick={() => onResume(item.id)}>
                        Resume
                      </ActionButton>
                    ) : null}
                    {item.status === "failed" ? (
                      <ActionButton label="Retry" onClick={() => onRetry(item.id)}>
                        <RefreshIcon className="h-3 w-3" />
                      </ActionButton>
                    ) : null}
                    {item.status === "uploading" || item.status === "queued" || item.status === "paused" ? (
                      <ActionButton label="Cancel" onClick={() => onCancel(item.id)}>
                        <CloseIcon className="h-3 w-3" />
                      </ActionButton>
                    ) : null}
                    {item.status === "failed" || item.status === "cancelled" || item.status === "succeeded" ? (
                      <ActionButton label="Remove" onClick={() => onRemove(item.id)}>
                        Remove
                      </ActionButton>
                    ) : null}
                  </div>
                </div>
                <div className="mt-2">
                  <UploadProgress upload={item} />
                </div>
                {item.error ? (
                  <p className="mt-2 text-[10px] font-semibold text-danger-500">{item.error}</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-7 items-center justify-center rounded-lg border border-border bg-card px-2 text-[10px] font-semibold text-muted-foreground transition hover:text-foreground"
      aria-label={label}
      title={label}
    >
      {children}
    </button>
  );
}
