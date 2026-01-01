import clsx from "clsx";

import type { DocumentStatus } from "../types";

const STATUS_STYLES: Record<
  DocumentStatus,
  {
    label: string;
    pill: string;
    dot: string;
  }
> = {
  processed: {
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
  uploaded: {
    label: "Uploaded",
    pill: "border-border bg-background text-muted-foreground",
    dot: "bg-muted-foreground",
  },
  archived: {
    label: "Archived",
    pill: "border-border bg-muted text-muted-foreground",
    dot: "bg-muted-foreground",
  },
};

export function StatusPill({ status }: { status: DocumentStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={clsx("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold", style.pill)}>
      <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}
