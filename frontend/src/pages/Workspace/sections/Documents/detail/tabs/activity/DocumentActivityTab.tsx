import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock,
  FileUp,
  PlayCircle,
  XCircle,
} from "lucide-react";

import { fetchWorkspaceRunsForDocument, type RunResource } from "@/api/runs/api";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useSession } from "@/providers/auth/SessionContext";
import {
  formatTimestamp,
  shortId,
} from "@/pages/Workspace/sections/Documents/shared/utils";
import type {
  DocumentActivityFilter,
} from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";
import type { RunStatus } from "@/types";

import { CommentComposer } from "../comments/components/CommentComposer";
import {
  useDocumentComments,
  type CommentDraft,
} from "../comments/hooks/useDocumentComments";

type CommentAuthor = NonNullable<
  ReturnType<typeof useDocumentComments>["comments"][number]["author"]
>;

type ActivityItem =
  | {
      key: string;
      kind: "event";
      type: "uploaded";
      timestamp: string;
      title: string;
      description?: string | null;
    }
  | {
      key: string;
      kind: "event";
      type: "run";
      timestamp: string;
      run: RunResource;
    }
  | {
      key: string;
      kind: "comment";
      type: "comment";
      timestamp: string;
      comment: ReturnType<typeof useDocumentComments>["comments"][number];
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

function buildInitials(name: string) {
  const parts = name.split(/[\s_-]+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function toEpoch(value: string) {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function formatRunStatus(value: string) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

function renderCommentBody(
  body: string,
  mentions: Array<{ name?: string | null; email: string }>,
) {
  const tokens = body.split(/(\s+)/);
  const mentionTokens = new Set<string>();
  mentions.forEach((mention) => {
    if (mention.name) {
      mentionTokens.add(`@${mention.name}`);
    }
    if (mention.email) {
      mentionTokens.add(`@${mention.email}`);
    }
  });

  return tokens.map((token, index) => {
    if (mentionTokens.has(token)) {
      return (
        <span
          key={`mention-${index}`}
          className="rounded bg-primary/10 px-1 text-primary"
        >
          {token}
        </span>
      );
    }
    return <span key={`token-${index}`}>{token}</span>;
  });
}

export function DocumentActivityTab({
  workspaceId,
  document,
  filter,
  onFilterChange,
}: {
  workspaceId: string;
  document: DocumentRow;
  filter: DocumentActivityFilter;
  onFilterChange: (filter: DocumentActivityFilter) => void;
}) {
  const session = useSession();
  const currentUser = useMemo<CommentAuthor>(
    () => ({
      id: session.user.id,
      name: session.user.display_name || session.user.email || null,
      email: session.user.email ?? "",
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );

  const commentsModel = useDocumentComments({
    workspaceId,
    documentId: document.id,
    currentUser,
  });

  const runsQuery = useQuery({
    queryKey: ["document-activity-runs", workspaceId, document.id],
    queryFn: ({ signal }) =>
      fetchWorkspaceRunsForDocument(workspaceId, document.id, signal),
    enabled: Boolean(workspaceId && document.id),
    staleTime: 30_000,
  });

  const allItems = useMemo<ActivityItem[]>(() => {
    const next: ActivityItem[] = [];

    next.push({
      key: `uploaded:${document.id}`,
      kind: "event",
      type: "uploaded",
      timestamp: document.createdAt,
      title: "Document uploaded",
      description: document.uploader?.name || document.uploader?.email || null,
    });

    (runsQuery.data ?? []).forEach((run) => {
      const timestamp = run.completed_at ?? run.started_at ?? run.created_at;
      next.push({
        key: `run:${run.id}`,
        kind: "event",
        type: "run",
        timestamp,
        run,
      });
    });

    commentsModel.comments.forEach((comment) => {
      next.push({
        key: `comment:${comment.id}`,
        kind: "comment",
        type: "comment",
        timestamp: comment.createdAt,
        comment,
      });
    });

    return next.sort((a, b) => toEpoch(a.timestamp) - toEpoch(b.timestamp));
  }, [
    commentsModel.comments,
    document.createdAt,
    document.id,
    document.uploader?.email,
    document.uploader?.name,
    runsQuery.data,
  ]);

  const visibleItems = useMemo(
    () =>
      allItems.filter((item) => {
        if (filter === "all") return true;
        if (filter === "comments") return item.kind === "comment";
        return item.kind === "event";
      }),
    [allItems, filter],
  );

  const activityCounts = useMemo(
    () => ({
      all: allItems.length,
      comments: allItems.filter((item) => item.kind === "comment").length,
      events: allItems.filter((item) => item.kind === "event").length,
    }),
    [allItems],
  );

  const isLoading =
    (runsQuery.isLoading || commentsModel.isLoading) && allItems.length === 0;
  const hasError = Boolean(runsQuery.error || commentsModel.error);

  const handleSubmitComment = (draft: CommentDraft) => {
    void commentsModel.submitComment(draft);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-muted/20">
      <div className="border-b border-border bg-background px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">Activity</div>
            <div className="text-xs text-muted-foreground">
              Collaboration thread and processing history for this document.
            </div>
          </div>
          <div className="flex items-center gap-2">
            <FilterChip
              active={filter === "all"}
              onClick={() => onFilterChange("all")}
              label={`All (${activityCounts.all})`}
            />
            <FilterChip
              active={filter === "comments"}
              onClick={() => onFilterChange("comments")}
              label={`Comments (${activityCounts.comments})`}
            />
            <FilterChip
              active={filter === "events"}
              onClick={() => onFilterChange("events")}
              label={`Events (${activityCounts.events})`}
            />
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-4 py-4">
        {hasError ? (
          <div className="mb-4 rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
            Some activity may be missing right now.
          </div>
        ) : null}

        {isLoading ? (
          <div className="space-y-4">
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex items-start gap-3">
                <Skeleton className="mt-1 h-8 w-8 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-44" />
                  <Skeleton className="h-4 w-full" />
                </div>
              </div>
            ))}
          </div>
        ) : visibleItems.length === 0 ? (
          <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
            No activity found for this filter.
          </div>
        ) : (
          <div className="space-y-3">
            {visibleItems.map((item) => {
              if (item.type === "uploaded") {
                return (
                  <ActivityCard
                    key={item.key}
                    icon={<FileUp className="h-4 w-4" />}
                    iconClassName="border-primary/40 bg-primary/5 text-primary"
                    title={item.title}
                    timestamp={item.timestamp}
                    description={
                      item.description ? (
                        <span className="text-muted-foreground">
                          Uploaded by{" "}
                          <span className="font-medium text-foreground">
                            {item.description}
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">
                          Uploaded
                        </span>
                      )
                    }
                  />
                );
              }

              if (item.type === "run") {
                const status = item.run.status as RunStatus;
                const tone = RUN_TONE[status];
                const DotIcon = tone?.Icon ?? PlayCircle;
                return (
                  <ActivityCard
                    key={item.key}
                    icon={<DotIcon className="h-4 w-4" />}
                    iconClassName={cn(
                      "border-border bg-muted/30 text-muted-foreground",
                      tone?.dot,
                    )}
                    title={
                      <div className="flex items-center gap-2">
                        <span className="font-mono">
                          Run {shortId(item.run.id)}
                        </span>
                        <Badge
                          variant="outline"
                          className={cn("capitalize", tone?.badge)}
                        >
                          {formatRunStatus(String(item.run.status))}
                        </Badge>
                      </div>
                    }
                    timestamp={item.timestamp}
                    description={
                      <div className="space-y-1">
                        {item.run.duration_seconds ? (
                          <div className="text-muted-foreground">
                            Duration{" "}
                            <span className="font-medium text-foreground">
                              {Math.round(item.run.duration_seconds)}s
                            </span>
                            {item.run.exit_code !== null &&
                            item.run.exit_code !== undefined ? (
                              <> · Exit {item.run.exit_code}</>
                            ) : null}
                          </div>
                        ) : (
                          <div className="text-muted-foreground">
                            Status: {formatRunStatus(String(item.run.status))}
                          </div>
                        )}
                        {item.run.failure_message ? (
                          <div className="rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                            {item.run.failure_message}
                          </div>
                        ) : null}
                      </div>
                    }
                  />
                );
              }

              const authorName =
                item.comment.author?.name ||
                item.comment.author?.email ||
                "Unknown";
              const initials = buildInitials(authorName);
              return (
                <div
                  key={item.key}
                  className={cn(
                    "rounded-lg border border-border bg-background p-3 shadow-sm",
                    item.comment.optimistic && "opacity-70",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="text-xs font-semibold">
                        {initials}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-semibold text-foreground">
                          {authorName}
                        </span>
                        <Badge variant="outline" className="text-[10px]">
                          Comment
                        </Badge>
                        <span>
                          {item.comment.optimistic
                            ? "Sending..."
                            : formatTimestamp(item.timestamp)}
                        </span>
                      </div>
                      <div className="mt-1 whitespace-pre-wrap text-sm text-foreground">
                        {renderCommentBody(
                          item.comment.body,
                          item.comment.mentions ?? [],
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {commentsModel.hasNextPage ? (
          <div className="mt-4">
            <Button
              size="sm"
              variant="outline"
              onClick={() => commentsModel.fetchNextPage()}
              disabled={commentsModel.isFetchingNextPage}
            >
              {commentsModel.isFetchingNextPage ? "Loading..." : "Load more comments"}
            </Button>
          </div>
        ) : null}
      </div>

      <Separator />
      <div className="bg-background px-4 py-3">
        <CommentComposer
          workspaceId={workspaceId}
          currentUser={currentUser}
          onSubmit={handleSubmitComment}
          isSubmitting={commentsModel.isSubmitting}
        />
        {commentsModel.submitError ? (
          <div className="mt-2 text-xs text-destructive">
            {commentsModel.submitError}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={active ? "secondary" : "outline"}
      className="h-8 text-xs"
      onClick={onClick}
    >
      {label}
    </Button>
  );
}

function ActivityCard({
  icon,
  iconClassName,
  title,
  timestamp,
  description,
}: {
  icon: ReactNode;
  iconClassName?: string;
  title: ReactNode;
  timestamp: string;
  description?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-3 shadow-sm">
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-full border",
            iconClassName,
          )}
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-medium text-foreground">{title}</div>
            <div className="text-xs text-muted-foreground">
              {formatTimestamp(timestamp)}
            </div>
          </div>
          {description ? (
            <div className="mt-1 text-sm">{description}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
