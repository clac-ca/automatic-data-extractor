import { stableId } from "@/pages/Workspace/sections/Documents/shared/utils";

import type {
  CommentAuthor,
  CommentMentionDraft,
} from "../activityTypes";
import type {
  ActivityComment,
  ActivityPendingAction,
  ActivityRecord,
  ActivityResponseData,
  ActivityThread,
} from "../model";

type OptimisticCommentInput = {
  workspaceId: string;
  documentId: string;
  threadId: string;
  currentUser: CommentAuthor;
  body: string;
  mentions: CommentMentionDraft[];
  pendingAction: ActivityPendingAction;
};

export function ensureActivityData(
  current: ActivityResponseData | undefined,
): ActivityResponseData {
  return current ?? { items: [] };
}

export function buildOptimisticComment({
  workspaceId,
  documentId,
  threadId,
  currentUser,
  body,
  mentions,
  pendingAction,
}: OptimisticCommentInput): ActivityComment {
  const now = new Date().toISOString();

  return {
    id: stableId(),
    workspaceId,
    documentId,
    threadId,
    body,
    author: {
      id: currentUser.id,
      name: currentUser.name,
      email: currentUser.email,
    },
    mentions: mentions.map((mention) => ({
      user: mention.user,
      start: mention.start,
      end: mention.end,
    })),
    createdAt: now,
    updatedAt: now,
    editedAt: pendingAction === "edit" ? now : null,
    optimistic: true,
    pendingAction,
  };
}

export function buildOptimisticThread({
  workspaceId,
  documentId,
  anchorType,
  anchorId,
  currentUser,
  body,
  mentions,
  activityAt,
  pendingAction,
}: {
  workspaceId: string;
  documentId: string;
  anchorType: "note" | "document" | "run";
  anchorId?: string | null;
  currentUser: CommentAuthor;
  body: string;
  mentions: CommentMentionDraft[];
  activityAt: string;
  pendingAction: Exclude<ActivityPendingAction, "edit">;
}): ActivityThread {
  const threadId = stableId();

  return {
    id: threadId,
    workspaceId,
    documentId,
    anchorType,
    anchorId: anchorId ?? null,
    activityAt,
    commentCount: 1,
    comments: [
      buildOptimisticComment({
        workspaceId,
        documentId,
        threadId,
        currentUser,
        body,
        mentions,
        pendingAction,
      }),
    ],
    optimistic: true,
    pendingAction,
  };
}

export function appendOptimisticNote(
  current: ActivityResponseData | undefined,
  note: Extract<ActivityRecord, { type: "note" }>,
): ActivityResponseData {
  const safeCurrent = ensureActivityData(current);

  return {
    ...safeCurrent,
    items: [...safeCurrent.items, note],
  };
}

export function attachThreadToActivityItem(
  current: ActivityResponseData | undefined,
  anchorType: "document" | "run",
  anchorId: string,
  thread: ActivityThread,
): ActivityResponseData {
  const safeCurrent = ensureActivityData(current);

  return {
    ...safeCurrent,
    items: safeCurrent.items.map((item) => {
      if (item.type !== anchorType || item.id !== anchorId) {
        return item;
      }

      return {
        ...item,
        thread,
      };
    }),
  };
}

export function appendCommentToThread(
  current: ActivityResponseData | undefined,
  threadId: string,
  comment: ActivityComment,
): ActivityResponseData {
  const safeCurrent = ensureActivityData(current);

  return {
    ...safeCurrent,
    items: safeCurrent.items.map((item) => {
      if (!item.thread || item.thread.id !== threadId) {
        return item;
      }

      return {
        ...item,
        thread: {
          ...item.thread,
          commentCount: item.thread.commentCount + 1,
          comments: [...item.thread.comments, comment].sort((left, right) =>
            left.createdAt.localeCompare(right.createdAt),
          ),
        },
      };
    }),
  };
}

export function updateCommentInActivity(
  current: ActivityResponseData | undefined,
  commentId: string,
  updater: (comment: ActivityComment) => ActivityComment,
): ActivityResponseData {
  const safeCurrent = ensureActivityData(current);

  return {
    ...safeCurrent,
    items: safeCurrent.items.map((item) => {
      if (!item.thread) {
        return item;
      }

      let changed = false;
      const comments = item.thread.comments.map((comment) => {
        if (comment.id !== commentId) {
          return comment;
        }

        changed = true;
        return updater(comment);
      });

      if (!changed) {
        return item;
      }

      return {
        ...item,
        thread: {
          ...item.thread,
          comments,
        },
      };
    }),
  };
}
