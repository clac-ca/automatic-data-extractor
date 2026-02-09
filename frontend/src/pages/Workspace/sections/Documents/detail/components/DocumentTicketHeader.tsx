import { useMemo } from "react";
import { ChevronLeft, PencilLine } from "lucide-react";

import { resolveApiUrl } from "@/api/client";
import { CloseIcon, RefreshIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { formatTimestamp, shortId } from "@/pages/Workspace/sections/Documents/shared/utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";
import type { RunStatus } from "@/types";

const RUN_STATUS_BADGE_STYLES: Record<RunStatus, string> = {
  queued: "border-border/60 bg-secondary text-secondary-foreground",
  running: "border-info/30 bg-info/10 text-info dark:bg-info/20",
  succeeded: "border-success/30 bg-success/10 text-success dark:bg-success/20",
  failed: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
  cancelled: "border-border/60 bg-muted text-muted-foreground",
};

function formatRunStatus(value: RunStatus) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

export function DocumentTicketHeader({
  workspaceId,
  document,
  onBack,
  onRenameRequest,
  onReprocessRequest,
  onCancelRunRequest,
  isRunActionPending = false,
}: {
  workspaceId: string;
  document: DocumentRow;
  onBack: () => void;
  onRenameRequest: () => void;
  onReprocessRequest: () => void;
  onCancelRunRequest: () => void;
  isRunActionPending?: boolean;
}) {
  const downloadHref = useMemo(
    () => resolveApiUrl(`/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`),
    [document.id, workspaceId],
  );
  const originalHref = useMemo(
    () => resolveApiUrl(
    `/api/v1/workspaces/${workspaceId}/documents/${document.id}/original/download`,
  ),
    [document.id, workspaceId],
  );
  const runStatus = document.lastRun?.status ?? null;
  const isRunActive = runStatus === "queued" || runStatus === "running";
  const runActionLabel = isRunActive ? "Cancel run" : "Reprocess";

  return (
    <div className="sticky top-0 z-20 border-b bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/90">
      <div className="flex flex-wrap items-start gap-3">
        <Button variant="ghost" size="sm" onClick={onBack} className="gap-1">
          <ChevronLeft className="h-4 w-4" />
          Back
        </Button>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              DOC-{shortId(document.id, 6)}
            </Badge>
            <span className="truncate text-sm font-semibold" title={document.name}>
              {document.name}
            </span>
            {runStatus ? (
              <Badge
                variant="outline"
                className={cn(
                  "capitalize",
                  RUN_STATUS_BADGE_STYLES[runStatus],
                )}
              >
                {formatRunStatus(runStatus)}
              </Badge>
            ) : null}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            Last activity: {formatTimestamp(document.activityAt)}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant={isRunActive ? "secondary" : "outline"}
            className="gap-1.5"
            onClick={isRunActive ? onCancelRunRequest : onReprocessRequest}
            disabled={isRunActionPending}
          >
            {isRunActive ? <CloseIcon className="h-4 w-4" /> : <RefreshIcon className="h-4 w-4" />}
            {runActionLabel}
          </Button>
          <Button size="sm" variant="ghost" className="gap-1.5" onClick={onRenameRequest}>
            <PencilLine className="h-4 w-4" />
            Rename
          </Button>
          <Button asChild size="sm" variant="secondary">
            <a href={downloadHref} target="_blank" rel="noreferrer">
              Download
            </a>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline">
                More
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <a href={originalHref} target="_blank" rel="noreferrer">
                  Download original
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}
