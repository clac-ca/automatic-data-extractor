import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { RunStatus } from "@/types";

const STATUS_BADGE_STYLES: Record<RunStatus, string> = {
  queued: "border-border/60 bg-secondary text-secondary-foreground",
  running: "border-border/60 bg-accent text-accent-foreground",
  succeeded: "border-primary/20 bg-primary/10 text-primary",
  failed: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
};

export function DocumentRunPhaseCell({
  status,
  uploadProgress,
}: {
  status: RunStatus | null;
  uploadProgress?: number | null;
}) {
  const showUpload = typeof uploadProgress === "number";
  const label = showUpload ? "Uploading" : status ? status.replace(/_/g, " ") : "No runs";
  const tone = status ? STATUS_BADGE_STYLES[status] : "border-border bg-muted text-muted-foreground";

  return (
    <div className="flex min-w-[120px] flex-col gap-1">
      <Badge variant="outline" className={cn("capitalize", tone)}>
        {label}
      </Badge>
      {showUpload ? (
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <div className="h-1.5 w-16 rounded-full bg-muted">
            <div
              className="h-1.5 rounded-full bg-primary"
              style={{ width: `${Math.max(0, Math.min(100, uploadProgress))}%` }}
            />
          </div>
          <span className="tabular-nums">{Math.round(uploadProgress)}%</span>
        </div>
      ) : null}
    </div>
  );
}
