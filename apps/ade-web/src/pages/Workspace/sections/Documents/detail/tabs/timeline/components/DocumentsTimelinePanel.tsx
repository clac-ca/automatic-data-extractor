import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNowStrict } from "date-fns";
import { CheckCircle2, Clock, FileUp, MessageSquareText, PlayCircle, XCircle } from "lucide-react";

import { listDocumentComments, type DocumentComment } from "@/api/documents";
import { fetchWorkspaceRunsForDocument, type RunResource } from "@/api/runs/api";
import { Badge } from "@/components/ui/badge";
import {
  Timeline,
  TimelineConnector,
  TimelineContent,
  TimelineDescription,
  TimelineDot,
  TimelineHeader,
  TimelineItem,
  TimelineTime,
  TimelineTitle,
} from "@/components/ui/timeline";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  fileTypeLabel,
  formatBytes,
  formatTimestamp,
  shortId,
} from "@/pages/Workspace/sections/Documents/shared/utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";
import type { RunStatus } from "@/types";

type DocumentTimelineItem =
  | {
      key: string;
      type: "uploaded";
      timestamp: string;
      title: string;
      description?: string | null;
    }
  | {
      key: string;
      type: "run";
      timestamp: string;
      run: RunResource;
    }
  | {
      key: string;
      type: "comment";
      timestamp: string;
      comment: DocumentComment;
    };

const RUN_TONE: Record<
  RunStatus,
  { dot: string; badge: string; Icon: typeof PlayCircle }
> = {
  queued: {
    dot: "border-border/60 bg-secondary text-secondary-foreground",
    badge: "border-border/60 bg-secondary text-secondary-foreground",
    Icon: Clock,
  },
  running: {
    dot: "border-info/30 bg-info/10 text-info dark:bg-info/20",
    badge: "border-info/30 bg-info/10 text-info dark:bg-info/20",
    Icon: PlayCircle,
  },
  succeeded: {
    dot: "border-success/30 bg-success/10 text-success dark:bg-success/20",
    badge: "border-success/30 bg-success/10 text-success dark:bg-success/20",
    Icon: CheckCircle2,
  },
  failed: {
    dot: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
    badge: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
    Icon: XCircle,
  },
};

function formatRunStatus(value: string) {
  if (!value) return "-";
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

function clampText(value: string, max = 160) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, Math.max(0, max - 1)).trimEnd()}…`;
}

function toEpoch(value: string) {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function formatRelativeTimestamp(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatDistanceToNowStrict(date, { addSuffix: true });
}

export function DocumentsTimelinePanel({
  workspaceId,
  document,
}: {
  workspaceId: string;
  document: DocumentRow;
}) {
  const runsQuery = useQuery({
    queryKey: ["document-timeline-runs", workspaceId, document.id],
    queryFn: ({ signal }) => fetchWorkspaceRunsForDocument(workspaceId, document.id, signal),
    enabled: Boolean(workspaceId && document.id),
    staleTime: 30_000,
  });

  const commentsQuery = useQuery({
    queryKey: ["document-timeline-comments", workspaceId, document.id],
    queryFn: ({ signal }) => listDocumentComments(workspaceId, document.id, { limit: 50 }, signal),
    enabled: Boolean(workspaceId && document.id),
    staleTime: 15_000,
  });

  const items = useMemo<DocumentTimelineItem[]>(() => {
    const next: DocumentTimelineItem[] = [];

    next.push({
      key: `uploaded:${document.id}`,
      type: "uploaded",
      timestamp: document.createdAt,
      title: "Uploaded",
      description: document.uploader?.name || document.uploader?.email || null,
    });

    (runsQuery.data ?? []).forEach((run) => {
      const timestamp = run.completed_at ?? run.started_at ?? run.created_at;
      next.push({
        key: `run:${run.id}`,
        type: "run",
        timestamp,
        run,
      });
    });

    (commentsQuery.data?.items ?? []).forEach((comment) => {
      next.push({
        key: `comment:${comment.id}`,
        type: "comment",
        timestamp: comment.createdAt,
        comment,
      });
    });

    // Chronological (oldest -> newest) reads like a ticket history.
    return next.sort((a, b) => toEpoch(a.timestamp) - toEpoch(b.timestamp));
  }, [commentsQuery.data?.items, document.createdAt, document.id, document.uploader?.email, document.uploader?.name, runsQuery.data]);

  const remoteCount = (runsQuery.data?.length ?? 0) + (commentsQuery.data?.items.length ?? 0);
  const isLoading = (runsQuery.isLoading || commentsQuery.isLoading) && remoteCount === 0;
  const hasError = Boolean(runsQuery.error || commentsQuery.error);
  const hasItems = items.length > 0;
  const lastActivityLabel = formatRelativeTimestamp(document.activityAt);
  const fileMetaLabel = `${fileTypeLabel(document.fileType)} · ${formatBytes(document.byteSize ?? 0)}`;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-muted/20">
      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="mx-auto w-full max-w-5xl">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <div className="text-sm font-semibold">Activity</div>
              <div className="text-xs text-muted-foreground">
                {hasItems ? (
                  <>
                    {items.length.toLocaleString()} event{items.length === 1 ? "" : "s"} · Last activity{" "}
                    <span title={formatTimestamp(document.activityAt)}>
                      {lastActivityLabel || formatTimestamp(document.activityAt)}
                    </span>
                  </>
                ) : (
                  "A running history of uploads, runs, and comments."
                )}
              </div>
            </div>
            <Badge variant="outline" className="w-fit bg-background">
              {fileMetaLabel}
            </Badge>
          </div>

          <div className="mt-4 rounded-xl border border-border bg-background shadow-sm">
            <div className="p-5">
              {hasError ? (
                <div className="mb-4 rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
                  Some activity may be missing right now.
                </div>
              ) : null}

              {isLoading ? (
                <div className="space-y-4">
                  {[0, 1, 2, 3].map((row) => (
                    <div key={row} className="flex items-start gap-3">
                      <Skeleton className="mt-1 h-8 w-8 rounded-full" />
                      <div className="flex-1 space-y-2">
                        <Skeleton className="h-3 w-48" />
                        <Skeleton className="h-4 w-full" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : items.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-sm text-muted-foreground">
                  No timeline events yet.
                </div>
              ) : (
                <Timeline className="gap-6 [--timeline-dot-size:1.25rem] [--timeline-connector-thickness:0.125rem]">
                  {items.map((item) => {
                if (item.type === "uploaded") {
                  return (
                    <TimelineItem key={item.key}>
                      <TimelineDot className="border-primary/40 bg-primary/5 text-primary">
                        <FileUp className="h-3.5 w-3.5" />
                      </TimelineDot>
                      <TimelineConnector className="bg-border/60" />
                      <TimelineContent>
                        <div className="rounded-lg border border-border/60 bg-background p-3 shadow-sm">
                          <TimelineHeader>
                            <TimelineTitle className="text-sm">Uploaded</TimelineTitle>
                            <TimelineTime
                              dateTime={item.timestamp}
                              title={formatTimestamp(item.timestamp)}
                              className="tabular-nums"
                            >
                              {formatRelativeTimestamp(item.timestamp) || formatTimestamp(item.timestamp)}
                            </TimelineTime>
                          </TimelineHeader>
                          <TimelineDescription className="text-sm">
                            {item.description ? (
                              <>
                                <span className="font-medium text-foreground">{item.description}</span>
                                <span className="text-muted-foreground">
                                  {" "}
                                  · {fileMetaLabel}
                                </span>
                              </>
                            ) : (
                              <>
                                {fileMetaLabel}
                              </>
                            )}
                          </TimelineDescription>
                        </div>
                      </TimelineContent>
                    </TimelineItem>
                  );
                }

                if (item.type === "comment") {
                  const author =
                    item.comment.author?.name ||
                    item.comment.author?.email ||
                    "Unknown";
                  return (
                    <TimelineItem key={item.key}>
                      <TimelineDot className="border-border bg-muted/30 text-muted-foreground">
                        <MessageSquareText className="h-3.5 w-3.5" />
                      </TimelineDot>
                      <TimelineConnector className="bg-border/60" />
                      <TimelineContent>
                        <div className="rounded-lg border border-border/60 bg-background p-3 shadow-sm">
                          <TimelineHeader>
                            <TimelineTitle className="flex flex-wrap items-center gap-2 text-sm">
                              Comment
                              <span className="text-xs font-normal text-muted-foreground">
                                by {author}
                              </span>
                            </TimelineTitle>
                            <TimelineTime
                              dateTime={item.timestamp}
                              title={formatTimestamp(item.timestamp)}
                              className="tabular-nums"
                            >
                              {formatRelativeTimestamp(item.timestamp) || formatTimestamp(item.timestamp)}
                            </TimelineTime>
                          </TimelineHeader>
                          <TimelineDescription className="whitespace-pre-wrap text-sm">
                            {clampText(item.comment.body, 260)}
                          </TimelineDescription>
                        </div>
                      </TimelineContent>
                    </TimelineItem>
                  );
                }

                const statusLabel = formatRunStatus(String(item.run.status));
                const status = item.run.status as RunStatus;
                const tone = RUN_TONE[status] ?? null;
                const DotIcon = tone?.Icon ?? PlayCircle;
                return (
                  <TimelineItem key={item.key}>
                    <TimelineDot className={cn("border-border bg-muted/30 text-muted-foreground", tone?.dot)}>
                      <DotIcon className="h-3.5 w-3.5" />
                    </TimelineDot>
                    <TimelineConnector className="bg-border/60" />
                    <TimelineContent>
                      <div className="rounded-lg border border-border/60 bg-background p-3 shadow-sm">
                        <TimelineHeader>
                          <TimelineTitle className="flex flex-wrap items-center gap-2 text-sm">
                            <span className="font-mono">Run {shortId(item.run.id)}</span>
                            <Badge
                              variant="outline"
                              className={cn("capitalize", tone?.badge)}
                            >
                              {statusLabel}
                            </Badge>
                          </TimelineTitle>
                          <TimelineTime
                            dateTime={item.timestamp}
                            title={formatTimestamp(item.timestamp)}
                            className="tabular-nums"
                          >
                            {formatRelativeTimestamp(item.timestamp) || formatTimestamp(item.timestamp)}
                          </TimelineTime>
                        </TimelineHeader>
                        <TimelineDescription className="text-sm">
                          {item.run.duration_seconds ? (
                            <span className="text-muted-foreground">
                              Duration{" "}
                              <span className="font-medium text-foreground">
                                {Math.round(item.run.duration_seconds)}s
                              </span>
                              {item.run.exit_code !== null && item.run.exit_code !== undefined ? (
                                <> · Exit {item.run.exit_code}</>
                              ) : null}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">Status: {statusLabel}</span>
                          )}

                          {item.run.failure_message ? (
                            <div className="mt-2 rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                              {clampText(item.run.failure_message, 240)}
                            </div>
                          ) : null}
                        </TimelineDescription>
                      </div>
                    </TimelineContent>
                  </TimelineItem>
                );
              })}
                </Timeline>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
