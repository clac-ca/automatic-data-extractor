import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { DocumentStatus } from "../../../types";

const STATUS_BADGE_STYLES: Record<DocumentStatus, string> = {
  uploading: "border-border/60 bg-muted text-muted-foreground",
  uploaded: "border-border/60 bg-secondary text-secondary-foreground",
  processing: "border-border/60 bg-accent text-accent-foreground",
  processed: "border-primary/20 bg-primary/10 text-primary",
  failed: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
  archived: "border-border/60 bg-secondary text-secondary-foreground",
};

export function DocumentStatusCell({
  status,
  uploadProgress,
}: {
  status: DocumentStatus;
  uploadProgress?: number | null;
}) {
  const tone = STATUS_BADGE_STYLES[status] ?? "border-border bg-muted text-muted-foreground";

  return (
    <div className="flex min-w-[120px] flex-col gap-1">
      <Badge variant="outline" className={cn("capitalize", tone)}>
        {status}
      </Badge>
      {status === "uploading" && typeof uploadProgress === "number" ? (
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
