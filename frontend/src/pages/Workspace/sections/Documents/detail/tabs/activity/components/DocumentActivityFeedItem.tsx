import type { ReactNode } from "react";
import { FileUp, PlayCircle } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatTimestamp, shortId } from "@/pages/Workspace/sections/Documents/shared/utils";
import type { RunStatus } from "@/types";

import {
  buildInitials,
  formatRunStatus,
  RUN_TONE,
  type ActivityItem,
} from "../model";

export function DocumentActivityFeedItem({ item }: { item: ActivityItem }) {
  if (item.type === "uploaded") {
    return (
      <ActivityCard
        icon={<FileUp className="h-4 w-4" />}
        iconClassName="border-primary/40 bg-primary/5 text-primary"
        title={item.title}
        timestamp={item.timestamp}
        description={
          item.description ? (
            <span className="text-muted-foreground">
              Uploaded by <span className="font-medium text-foreground">{item.description}</span>
            </span>
          ) : (
            <span className="text-muted-foreground">Uploaded</span>
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
        icon={<DotIcon className="h-4 w-4" />}
        iconClassName={cn("border-border bg-muted/30 text-muted-foreground", tone?.dot)}
        title={
          <div className="flex items-center gap-2">
            <span className="font-mono">Run {shortId(item.run.id)}</span>
            <Badge variant="outline" className={cn("capitalize", tone?.badge)}>
              {formatRunStatus(String(item.run.status))}
            </Badge>
          </div>
        }
        timestamp={item.timestamp}
        description={<RunDescription item={item} />}
      />
    );
  }

  const authorName = item.comment.author?.name || item.comment.author?.email || "Unknown";

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-background p-3 shadow-sm",
        item.comment.optimistic && "opacity-70",
      )}
    >
      <div className="flex items-start gap-3">
        <Avatar className="h-8 w-8">
          <AvatarFallback className="text-xs font-semibold">{buildInitials(authorName)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{authorName}</span>
            <Badge variant="outline" className="text-[10px]">
              Comment
            </Badge>
            <span>{item.comment.optimistic ? "Sending..." : formatTimestamp(item.timestamp)}</span>
          </div>
          <div className="mt-1 whitespace-pre-wrap text-sm text-foreground">
            {renderCommentBody(item.comment.body, item.comment.mentions ?? [])}
          </div>
        </div>
      </div>
    </div>
  );
}

function RunDescription({ item }: { item: Extract<ActivityItem, { type: "run" }> }) {
  if (item.run.duration_seconds) {
    return (
      <div className="space-y-1">
        <div className="text-muted-foreground">
          Duration <span className="font-medium text-foreground">{Math.round(item.run.duration_seconds)}s</span>
          {item.run.exit_code !== null && item.run.exit_code !== undefined ? <> · Exit {item.run.exit_code}</> : null}
        </div>
        {item.run.failure_message ? (
          <div className="rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {item.run.failure_message}
          </div>
        ) : null}
      </div>
    );
  }

  return <div className="text-muted-foreground">Status: {formatRunStatus(String(item.run.status))}</div>;
}

function renderCommentBody(body: string, mentions: Array<{ name?: string | null; email: string }>) {
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
    if (!mentionTokens.has(token)) {
      return <span key={`token-${index}`}>{token}</span>;
    }

    return (
      <span key={`mention-${index}`} className="rounded bg-primary/10 px-1 text-primary">
        {token}
      </span>
    );
  });
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
            <div className="text-xs text-muted-foreground">{formatTimestamp(timestamp)}</div>
          </div>
          {description ? <div className="mt-1 text-sm">{description}</div> : null}
        </div>
      </div>
    </div>
  );
}
