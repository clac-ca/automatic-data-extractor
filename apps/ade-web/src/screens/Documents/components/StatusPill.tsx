import clsx from "clsx";

import type { DocumentQueueReason, DocumentQueueState, DocumentStatus } from "../types";

export const STATUS_STYLES: Record<
  DocumentStatus,
  {
    label: string;
    pill: string;
    dot: string;
  }
> = {
  ready: {
    label: "Processed",
    pill: "border-success-200 bg-success-50 text-success-700",
    dot: "bg-success-500",
  },
  processing: {
    label: "Processing",
    pill: "border-warning-200 bg-warning-50 text-warning-700",
    dot: "bg-warning-500",
  },
  failed: {
    label: "Failed",
    pill: "border-danger-200 bg-danger-50 text-danger-700",
    dot: "bg-danger-500",
  },
  queued: {
    label: "Queued",
    pill: "border-border bg-background text-muted-foreground",
    dot: "bg-muted-foreground",
  },
  archived: {
    label: "Archived",
    pill: "border-border bg-muted text-muted-foreground",
    dot: "bg-muted-foreground",
  },
};

export function resolveStatusLabel(
  status: DocumentStatus,
  queueState?: DocumentQueueState | null,
  queueReason?: DocumentQueueReason | null,
) {
  if (status === "queued") {
    return resolveQueuedLabel(queueState, queueReason);
  }
  return STATUS_STYLES[status].label;
}

export function StatusPill({
  status,
  queueState,
  queueReason,
}: {
  status: DocumentStatus;
  queueState?: DocumentQueueState | null;
  queueReason?: DocumentQueueReason | null;
}) {
  const style = STATUS_STYLES[status];
  const label = resolveStatusLabel(status, queueState, queueReason);
  return (
    <span className={clsx("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold", style.pill)}>
      <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
      {label}
    </span>
  );
}

function resolveQueuedLabel(
  queueState: DocumentQueueState | null | undefined,
  queueReason: DocumentQueueReason | null | undefined,
) {
  if (queueState === "queued") return "Queued";
  if (queueState !== "waiting") return "Queued";
  switch (queueReason) {
    case "processing_paused":
      return "Processing paused";
    case "queue_full":
      return "Waiting for capacity";
    case "no_active_configuration":
      return "Waiting for configuration";
    default:
      return "Waiting to start";
  }
}
