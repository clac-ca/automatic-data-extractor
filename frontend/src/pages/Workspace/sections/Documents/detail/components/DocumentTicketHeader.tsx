import { useMemo } from "react";
import { ChevronLeft, PencilLine } from "lucide-react";

import { resolveApiUrl } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatTimestamp, shortId } from "@/pages/Workspace/sections/Documents/shared/utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";
import type { RunStatus } from "@/types";

const RUN_STATUS_BADGE_STYLES: Record<RunStatus, string> = {
  queued: "border-border/60 bg-secondary text-secondary-foreground",
  running: "border-info/30 bg-info/10 text-info dark:bg-info/20",
  succeeded: "border-success/30 bg-success/10 text-success dark:bg-success/20",
  failed: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
};

function formatRunStatus(value: RunStatus) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

function resolveNormalizedDownloadState(document: DocumentRow): {
  href: string | null;
  label: string;
} {
  const status = document.lastRun?.status ?? null;
  const runId = document.lastRun?.id ?? null;

  if (status === "succeeded" && runId) {
    return {
      href: resolveApiUrl(`/api/v1/runs/${runId}/output/download`),
      label: "Download normalized output",
    };
  }

  if (status === "failed") {
    return { href: null, label: "Latest run failed; output unavailable" };
  }

  if (status === "running" || status === "queued") {
    return { href: null, label: "Output not ready yet" };
  }

  return { href: null, label: "No normalized output available yet" };
}

export function DocumentTicketHeader({
  workspaceId,
  document,
  onBack,
  onRenameRequest,
}: {
  workspaceId: string;
  document: DocumentRow;
  onBack: () => void;
  onRenameRequest: () => void;
}) {
  const normalizedDownload = useMemo(
    () => resolveNormalizedDownloadState(document),
    [document],
  );
  const originalHref = resolveApiUrl(
    `/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`,
  );
  const runStatus = document.lastRun?.status ?? null;

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
          <Button size="sm" variant="ghost" className="gap-1.5" onClick={onRenameRequest}>
            <PencilLine className="h-4 w-4" />
            Rename
          </Button>
          {normalizedDownload.href ? (
            <Button asChild size="sm" variant="secondary">
              <a href={normalizedDownload.href} target="_blank" rel="noreferrer">
                Download normalized
              </a>
            </Button>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              disabled
              title={normalizedDownload.label}
            >
              Download normalized
            </Button>
          )}
          <Button asChild size="sm" variant="outline">
            <a href={originalHref} target="_blank" rel="noreferrer">
              Download original
            </a>
          </Button>
        </div>
      </div>
    </div>
  );
}
