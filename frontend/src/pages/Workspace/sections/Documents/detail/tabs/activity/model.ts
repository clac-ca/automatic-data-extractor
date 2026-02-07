import {
  CheckCircle2,
  Clock,
  PlayCircle,
  XCircle,
} from "lucide-react";

import type { RunResource } from "@/api/runs/api";
import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";
import type { RunStatus } from "@/types";

import type { DocumentCommentItem } from "../comments/hooks/useDocumentComments";

export type ActivityItem =
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
      comment: DocumentCommentItem;
    };

export const RUN_TONE: Record<
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
  cancelled: {
    dot: "border-border/60 bg-muted text-muted-foreground",
    badge: "border-border/60 bg-muted text-muted-foreground",
    Icon: XCircle,
  },
};

function toEpoch(value: string) {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

export function buildInitials(name: string) {
  const parts = name.split(/[\s_-]+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export function formatRunStatus(value: string) {
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

export function buildActivityItems(
  document: DocumentRow,
  runs: RunResource[],
  comments: DocumentCommentItem[],
): ActivityItem[] {
  const items: ActivityItem[] = [
    {
      key: `uploaded:${document.id}`,
      kind: "event",
      type: "uploaded",
      timestamp: document.createdAt,
      title: "Document uploaded",
      description: document.uploader?.name || document.uploader?.email || null,
    },
  ];

  runs.forEach((run) => {
    items.push({
      key: `run:${run.id}`,
      kind: "event",
      type: "run",
      timestamp: run.completed_at ?? run.started_at ?? run.created_at,
      run,
    });
  });

  comments.forEach((comment) => {
    items.push({
      key: `comment:${comment.id}`,
      kind: "comment",
      type: "comment",
      timestamp: comment.createdAt,
      comment,
    });
  });

  return items.sort((a, b) => toEpoch(a.timestamp) - toEpoch(b.timestamp));
}

export function filterActivityItems(
  items: ActivityItem[],
  filter: DocumentActivityFilter,
): ActivityItem[] {
  if (filter === "all") return items;
  if (filter === "comments") {
    return items.filter((item) => item.kind === "comment");
  }
  return items.filter((item) => item.kind === "event");
}

export function getActivityCounts(items: ActivityItem[]) {
  const comments = items.filter((item) => item.kind === "comment").length;
  const events = items.length - comments;
  return {
    all: items.length,
    comments,
    events,
  };
}
