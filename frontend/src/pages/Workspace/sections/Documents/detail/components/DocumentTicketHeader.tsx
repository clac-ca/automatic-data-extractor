import { useMemo } from "react";
import { ChevronLeft, Download, MoreHorizontal } from "lucide-react";

import { resolveApiUrl } from "@/api/client";
import { CloseIcon, RefreshIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
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
  onRestoreRequest,
  onReprocessRequest,
  onCancelRunRequest,
  isRunActionPending = false,
  showViewSwitch = false,
}: {
  workspaceId: string;
  document: DocumentRow;
  onBack: () => void;
  onRenameRequest: () => void;
  onRestoreRequest: () => void;
  onReprocessRequest: () => void;
  onCancelRunRequest: () => void;
  isRunActionPending?: boolean;
  showViewSwitch?: boolean;
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
  const isArchived = Boolean(document.deletedAt);
  const primaryActionLabel = isRunActive ? "Cancel run" : isArchived ? "Restore" : "Reprocess";
  const onPrimaryAction = isRunActive
    ? onCancelRunRequest
    : isArchived
      ? onRestoreRequest
      : onReprocessRequest;

  return (
    <div className="sticky top-0 z-20 border-b bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/90">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onBack}
          aria-label="Back"
          title="Back"
          className="size-8 rounded-full"
        >
          <ChevronLeft data-icon="inline-start" />
        </Button>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              className="truncate rounded-sm text-left text-sm font-semibold leading-5 hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              title="Rename"
              onClick={onRenameRequest}
            >
              {document.name}
            </button>
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
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {showViewSwitch ? (
            <TabsList className="flex items-center rounded-full border border-border bg-muted/40 p-1">
              <TabsTrigger
                value="activity"
                className="rounded-full px-3 py-1 text-xs text-muted-foreground aria-selected:bg-background aria-selected:text-foreground aria-selected:shadow-sm"
              >
                Chat
              </TabsTrigger>
              <TabsTrigger
                value="preview"
                className="rounded-full px-3 py-1 text-xs text-muted-foreground aria-selected:bg-background aria-selected:text-foreground aria-selected:shadow-sm"
              >
                Preview
              </TabsTrigger>
            </TabsList>
          ) : null}
          <Button
            size="sm"
            variant={isRunActive ? "secondary" : "outline"}
            className="gap-1.5 rounded-full"
            onClick={onPrimaryAction}
            disabled={isRunActionPending}
          >
            {isRunActive ? <CloseIcon data-icon="inline-start" /> : <RefreshIcon data-icon="inline-start" />}
            {primaryActionLabel}
          </Button>
          <Button asChild size="sm" variant="secondary" className="gap-1.5 rounded-full">
            <a href={downloadHref} target="_blank" rel="noreferrer">
              <Download data-icon="inline-start" />
              Download
            </a>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon" variant="outline" className="size-8 rounded-full" aria-label="More">
                <MoreHorizontal data-icon="inline-start" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel className="max-w-64">
                <span className="block truncate text-xs font-normal text-muted-foreground">
                  DOC-{shortId(document.id, 6)}
                </span>
                <span className="block truncate text-xs font-normal text-muted-foreground">
                  {formatTimestamp(document.activityAt)}
                </span>
                {document.lastRun?.id ? (
                  <span className="block truncate font-mono text-xs font-normal text-muted-foreground">
                    Run {shortId(document.lastRun.id)}
                  </span>
                ) : null}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <a href={originalHref} target="_blank" rel="noreferrer">
                  <Download />
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
