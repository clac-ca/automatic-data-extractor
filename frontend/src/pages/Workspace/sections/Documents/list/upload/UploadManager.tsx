import clsx from "clsx";
import { useMemo, useState, type ReactNode } from "react";

import type { DocumentUploadResponse } from "@/api/documents";
import type { DocumentConflictMode } from "@/api/documents/uploads";
import type { UploadManagerItem, UploadManagerSummary } from "./useUploadManager";
import { AlertTriangleIcon, CloseIcon, RefreshIcon, UploadIcon } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { formatBytes } from "../../shared/utils";
import { UploadProgress } from "./UploadProgress";

type UploadItem = UploadManagerItem<DocumentUploadResponse>;

export function UploadManager({
  items,
  summary,
  onPause,
  onResume,
  onRetry,
  onResolveConflict,
  onResolveAllConflicts,
  onCancel,
  onRemove,
  onClearCompleted,
}: {
  items: UploadItem[];
  summary: UploadManagerSummary;
  onPause: (uploadId: string) => void;
  onResume: (uploadId: string) => void;
  onRetry: (uploadId: string) => void;
  onResolveConflict: (uploadId: string, mode: DocumentConflictMode) => void;
  onResolveAllConflicts: (mode: DocumentConflictMode) => void;
  onCancel: (uploadId: string) => void;
  onRemove: (uploadId: string) => void;
  onClearCompleted: () => void;
}) {
  const [open, setOpen] = useState(false);
  const hasUploads = summary.totalCount > 0;
  const completedCount = summary.completedCount;
  const hasConflicts = summary.conflictCount > 0;

  const summaryLabel = useMemo(() => {
    if (!hasUploads) return "Uploads";
    if (summary.conflictCount > 0) {
      return `${summary.conflictCount} conflict${summary.conflictCount === 1 ? "" : "s"}`;
    }
    const active = summary.uploadingCount + summary.queuedCount + summary.pausedCount;
    return active > 0 ? `${active} in progress` : `${summary.succeededCount} completed`;
  }, [hasUploads, summary]);

  if (!hasUploads) {
    return null;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={clsx(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            hasConflicts
              ? "border-warning/40 bg-warning/10 text-warning hover:bg-warning/15 hover:text-warning"
              : open
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground",
          )}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <UploadIcon className="h-4 w-4" />
          {summaryLabel}
          <span
            className={clsx(
              "rounded-full px-1.5 py-0.5 text-[10px]",
              hasConflicts ? "bg-warning/15 text-warning" : "bg-muted text-muted-foreground",
            )}
          >
            {summary.totalCount}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={8}
        collisionPadding={12}
        className="z-[var(--app-z-popover)] w-[22rem] max-w-[calc(100vw-1.5rem)] rounded-2xl border border-border bg-card p-4 shadow-lg"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Upload manager</p>
            <p className="text-[11px] text-muted-foreground">
              {summary.conflictCount > 0
                ? `${summary.conflictCount} conflict${summary.conflictCount === 1 ? "" : "s"} need attention`
                : summary.uploadingCount > 0
                  ? `${summary.uploadingCount} uploading`
                  : "All uploads paused or complete"}
            </p>
          </div>
          {completedCount > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onClearCompleted()}
              className="h-7 px-2 text-[11px]"
            >
              Clear completed
            </Button>
          ) : null}
        </div>

        {hasConflicts ? (
          <div className="mt-3 space-y-2">
            <Alert
              tone="warning"
              heading="Duplicate names detected"
              icon={<AlertTriangleIcon className="h-4 w-4" />}
              className="text-[11px]"
            >
              Choose how to continue uploads that match existing document names.
            </Alert>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button
                type="button"
                size="sm"
                className="h-7 justify-start px-2 text-[11px]"
                onClick={() => onResolveAllConflicts("upload_new_version")}
              >
                Replace existing for all
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="h-7 justify-start px-2 text-[11px]"
                onClick={() => onResolveAllConflicts("keep_both")}
              >
                Keep both for all
              </Button>
            </div>
          </div>
        ) : null}

        <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
          <span>
            {summary.uploadedBytes > 0 ? formatBytes(summary.uploadedBytes) : "0 B"} /{" "}
            {summary.totalBytes > 0 ? formatBytes(summary.totalBytes) : "0 B"}
          </span>
          <span className="tabular-nums">{summary.percent}%</span>
        </div>
        <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
          <div
            className="h-1.5 rounded-full bg-primary"
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
              {item.error && item.status !== "conflict" ? (
                <p className="mt-2 text-[10px] font-semibold text-destructive">{item.error}</p>
              ) : null}
              {item.status === "conflict" ? (
                <ConflictResolution
                  item={item}
                  onResolveConflict={onResolveConflict}
                  onCancel={onCancel}
                />
              ) : null}
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ConflictResolution({
  item,
  onResolveConflict,
  onCancel,
}: {
  item: UploadItem;
  onResolveConflict: (uploadId: string, mode: DocumentConflictMode) => void;
  onCancel: (uploadId: string) => void;
}) {
  return (
    <div className="mt-2 rounded-lg border border-warning/30 bg-warning/5 p-2">
      <div className="flex items-start gap-2">
        <AlertTriangleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold text-warning">This file already exists</p>
          <p className="text-[10px] text-muted-foreground">
            {item.conflict?.message ?? "Choose to replace the existing document or keep both files."}
          </p>
        </div>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <Button
          type="button"
          size="sm"
          className="h-7 justify-start px-2 text-[11px]"
          onClick={() => onResolveConflict(item.id, "upload_new_version")}
        >
          Replace existing
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="h-7 justify-start px-2 text-[11px]"
          onClick={() => onResolveConflict(item.id, "keep_both")}
        >
          Keep both files
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 justify-start px-2 text-[11px] sm:col-span-2"
          onClick={() => onCancel(item.id)}
        >
          Cancel upload
        </Button>
      </div>
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
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClick}
      className="h-7 px-2 text-[10px] text-muted-foreground hover:text-foreground"
      aria-label={label}
      title={label}
    >
      {children}
    </Button>
  );
}
