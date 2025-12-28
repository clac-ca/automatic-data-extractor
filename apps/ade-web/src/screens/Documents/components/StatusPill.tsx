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
  ready: {
    label: "Ready",
    pill: "border-emerald-200 bg-emerald-50 text-emerald-700",
    dot: "bg-emerald-500",
  },
  processing: {
    label: "Processing",
    pill: "border-amber-200 bg-amber-50 text-amber-700",
    dot: "bg-amber-500",
  },
  failed: {
    label: "Failed",
    pill: "border-rose-200 bg-rose-50 text-rose-700",
    dot: "bg-rose-500",
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

export function StatusPill({ status }: { status: DocumentStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={clsx("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-semibold", style.pill)}>
      <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}
