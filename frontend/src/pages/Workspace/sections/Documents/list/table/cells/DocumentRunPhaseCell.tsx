import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { RunStatus } from "@/types";

const STATUS_TONES: Record<RunStatus, string> = {
  queued: "border-secondary bg-secondary text-secondary-foreground",
  running: "border-info/40 bg-info/15 text-info dark:bg-info/20",
  succeeded: "border-success/40 bg-success/15 text-success dark:bg-success/20",
  failed: "border-destructive/40 bg-destructive/15 text-destructive dark:bg-destructive/20",
  cancelled: "border-muted bg-muted text-muted-foreground",
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
  const tone = status ? STATUS_TONES[status] : "border-muted bg-muted text-muted-foreground";

  return (
    <div className="flex min-w-[140px] flex-col gap-1">
      <Badge
        variant="outline"
        className={cn("h-7 w-fit min-w-[112px] rounded-md px-2 text-[11px] font-medium capitalize shadow-xs", tone)}
      >
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
