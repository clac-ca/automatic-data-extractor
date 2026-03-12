import {
  CheckCircle2,
  Clock,
  FileUp,
  MessageSquareText,
  PlayCircle,
  XCircle,
} from "lucide-react";

import type {
  DocumentActivityDocumentItem,
  DocumentActivityResponse,
  DocumentActivityRun,
  DocumentActivityThread,
  DocumentComment,
} from "@/api/documents";
import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { RunStatus } from "@/types";

export type ActivityPendingAction = "create" | "reply" | "edit";

export type ActivityComment = DocumentComment & {
  optimistic?: boolean;
  pendingAction?: ActivityPendingAction;
};

export type ActivityThread = Omit<DocumentActivityThread, "comments"> & {
  comments: ActivityComment[];
  optimistic?: boolean;
  pendingAction?: Exclude<ActivityPendingAction, "edit">;
};

export type ActivityRecord =
  | {
      key: string;
      replyTargetKey: string;
      id: string;
      type: "document";
      activityAt: string;
      title: string;
      uploader: DocumentActivityDocumentItem["uploader"];
      thread: ActivityThread | null;
    }
  | {
      key: string;
      replyTargetKey: string;
      id: string;
      type: "run";
      activityAt: string;
      run: DocumentActivityRun;
      thread: ActivityThread | null;
    }
  | {
      key: string;
      replyTargetKey: string;
      id: string;
      type: "note";
      activityAt: string;
      thread: ActivityThread;
    };

export type ActivityItem = ActivityRecord;

export type ActivityResponseData = {
  items: ActivityRecord[];
};

export const ACTIVITY_ICON = {
  document: FileUp,
  note: MessageSquareText,
} as const;

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

function typePriority(type: ActivityItem["type"]) {
  switch (type) {
    case "document":
      return 0;
    case "run":
      return 1;
    case "note":
      return 2;
  }
}

function parseAnchorId(rawId: string, fallback: string) {
  const [, parsed] = rawId.split(":", 2);
  return parsed || fallback;
}

function sortComments(comments: ActivityComment[]) {
  return [...comments].sort((left, right) => {
    const timeDelta = toEpoch(left.createdAt) - toEpoch(right.createdAt);
    if (timeDelta !== 0) return timeDelta;
    return left.id.localeCompare(right.id);
  });
}

function sortItems(items: ActivityRecord[]) {
  return [...items].sort((left, right) => {
    const timeDelta = toEpoch(left.activityAt) - toEpoch(right.activityAt);
    if (timeDelta !== 0) return timeDelta;

    const priorityDelta = typePriority(left.type) - typePriority(right.type);
    if (priorityDelta !== 0) return priorityDelta;

    return left.key.localeCompare(right.key);
  });
}

function normalizeComment(comment: DocumentComment): ActivityComment {
  return {
    ...comment,
    mentions: [...(comment.mentions ?? [])].sort((left, right) => left.start - right.start),
  };
}

function normalizeThread(thread: DocumentActivityThread): ActivityThread {
  const comments = sortComments((thread.comments ?? []).map(normalizeComment));
  return {
    ...thread,
    comments,
    commentCount: thread.commentCount ?? comments.length,
  };
}

export function normalizeActivityResponse(
  response: DocumentActivityResponse,
): ActivityResponseData {
  const items = response.items.map<ActivityRecord>((item) => {
    switch (item.type) {
      case "document": {
        const id = parseAnchorId(item.id, item.id);
        return {
          key: item.id,
          replyTargetKey: item.id,
          id,
          type: "document",
          activityAt: item.activityAt,
          title: item.title,
          uploader: item.uploader ?? null,
          thread: item.thread ? normalizeThread(item.thread) : null,
        };
      }
      case "run": {
        const id = parseAnchorId(item.id, item.run.id);
        return {
          key: item.id,
          replyTargetKey: item.id,
          id,
          type: "run",
          activityAt: item.activityAt,
          run: item.run,
          thread: item.thread ? normalizeThread(item.thread) : null,
        };
      }
      case "note":
        return {
          key: item.id,
          replyTargetKey: item.id,
          id: item.thread.id,
          type: "note",
          activityAt: item.activityAt,
          thread: normalizeThread(item.thread),
        };
    }
  });

  return {
    items: sortItems(items),
  };
}

export function buildActivityItems(data: ActivityResponseData): ActivityItem[] {
  return sortItems(data.items);
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

export function filterActivityItems(
  items: ActivityItem[],
  filter: DocumentActivityFilter,
): ActivityItem[] {
  if (filter === "all") return items;
  if (filter === "comments") {
    return items.filter((item) => item.type === "note" || Boolean(item.thread));
  }
  return items.filter((item) => item.type !== "note");
}
