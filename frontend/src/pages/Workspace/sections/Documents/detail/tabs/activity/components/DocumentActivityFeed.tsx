import { useState } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";

import type {
  ActivityCurrentUser,
  ActivityReplyTarget,
  CommentEditDraft,
  NoteDraft,
  ThreadReplyDraft,
} from "../activityTypes";
import type { ActivityComment, ActivityItem } from "../model";
import { DocumentActivityFeedItem } from "./DocumentActivityFeedItem";

function getClusterComment(item?: ActivityItem): ActivityComment | null {
  if (!item || item.type !== "note") {
    return null;
  }

  return item.thread.comments[0] ?? null;
}

function hasSameAuthor(left: ActivityComment | null, right: ActivityComment | null) {
  const leftAuthor = left?.author?.id ?? left?.author?.email ?? null;
  const rightAuthor = right?.author?.id ?? right?.author?.email ?? null;
  return Boolean(leftAuthor && rightAuthor && leftAuthor === rightAuthor);
}

function isCloseInTime(left: ActivityComment | null, right: ActivityComment | null) {
  if (!left || !right) {
    return false;
  }

  const leftTime = new Date(left.createdAt).getTime();
  const rightTime = new Date(right.createdAt).getTime();

  if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
    return false;
  }

  return Math.abs(rightTime - leftTime) <= 15 * 60 * 1000;
}

function getItemTime(item?: ActivityItem): string | null {
  if (!item) {
    return null;
  }

  if (item.type === "note") {
    return item.thread.comments[0]?.createdAt ?? item.activityAt;
  }

  return item.activityAt;
}

function isCloseItemTime(left: ActivityItem | undefined, right: ActivityItem) {
  const leftValue = getItemTime(left);
  const rightValue = getItemTime(right);

  if (!leftValue || !rightValue) {
    return false;
  }

  const leftTime = new Date(leftValue).getTime();
  const rightTime = new Date(rightValue).getTime();

  if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
    return false;
  }

  return Math.abs(rightTime - leftTime) <= 15 * 60 * 1000;
}

function isSameCalendarDay(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

function formatTimeSeparator(value: string | null) {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  const time = date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

  if (isSameCalendarDay(date, now)) {
    return `Today, ${time}`;
  }

  if (isSameCalendarDay(date, yesterday)) {
    return `Yesterday, ${time}`;
  }

  return `${date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric",
  })}, ${time}`;
}

export function DocumentActivityFeed({
  workspaceId,
  currentUser,
  items,
  isLoading,
  hasError,
  showDiscussions,
  activeReplyTargetKey,
  replyDraftsByTargetKey,
  submittingReplyTargetKey,
  replyErrorTargetKey,
  activeEditCommentId,
  editDraftsByCommentId,
  submittingEditCommentId,
  editErrorCommentId,
  editErrorMessage,
  deletingCommentId,
  deleteErrorCommentId,
  deleteErrorMessage,
  onStartReply,
  onCancelReply,
  onReplyDraftChange,
  onSubmitReply,
  onStartEdit,
  onCancelEdit,
  onEditDraftChange,
  onSubmitEdit,
  onDeleteComment,
}: {
  workspaceId: string;
  currentUser: ActivityCurrentUser;
  items: ActivityItem[];
  isLoading: boolean;
  hasError: boolean;
  showDiscussions: boolean;
  activeReplyTargetKey: string | null;
  replyDraftsByTargetKey: Record<string, NoteDraft>;
  submittingReplyTargetKey: string | null;
  replyErrorTargetKey: string | null;
  activeEditCommentId: string | null;
  editDraftsByCommentId: Record<string, NoteDraft>;
  submittingEditCommentId: string | null;
  editErrorCommentId: string | null;
  editErrorMessage?: string | null;
  deletingCommentId: string | null;
  deleteErrorCommentId: string | null;
  deleteErrorMessage?: string | null;
  onStartReply: (target: ActivityReplyTarget) => void;
  onCancelReply: () => void;
  onReplyDraftChange: (targetKey: string, draft: NoteDraft) => void;
  onSubmitReply: (draft: ThreadReplyDraft) => Promise<unknown> | void;
  onStartEdit: (commentId: string) => void;
  onCancelEdit: () => void;
  onEditDraftChange: (commentId: string, draft: NoteDraft) => void;
  onSubmitEdit: (draft: CommentEditDraft) => Promise<unknown> | void;
  onDeleteComment: (commentId: string) => Promise<unknown>;
}) {
  const [deleteTarget, setDeleteTarget] = useState<{
    commentId: string;
    authorName: string;
    body: string;
  } | null>(null);
  const isDeletingActiveTarget = deleteTarget?.commentId === deletingCommentId;
  const deleteDialogError =
    deleteTarget && deleteErrorCommentId === deleteTarget.commentId ? deleteErrorMessage : null;

  return (
    <>
      <div className="min-h-0 flex-1 overflow-auto bg-background px-4 pt-6 pb-32">
        {hasError && !isLoading ? (
          <div className="mx-auto mb-4 max-w-3xl rounded-xl border border-border/70 bg-card/95 p-3 text-sm text-muted-foreground shadow-sm">
            Activity could not be fully loaded right now.
          </div>
        ) : null}

        {isLoading ? <LoadingState /> : null}
        {!isLoading && items.length === 0 ? <EmptyState /> : null}
        {!isLoading && items.length > 0 ? (
          <div className="mx-auto flex max-w-5xl flex-col gap-4">
            {items.map((item, index) => {
              const comment = getClusterComment(item);
              const previousComment = getClusterComment(items[index - 1]);
              const nextComment = getClusterComment(items[index + 1]);
              const isClusteredWithPrevious =
                hasSameAuthor(previousComment, comment) && isCloseInTime(previousComment, comment);
              const isClusteredWithNext =
                hasSameAuthor(comment, nextComment) && isCloseInTime(comment, nextComment);
              const showTimeSeparator = index === 0 || !isCloseItemTime(items[index - 1], item);
              const timeSeparatorLabel = showTimeSeparator
                ? formatTimeSeparator(getItemTime(item))
                : null;

              return (
                <div key={item.key} className="flex flex-col gap-2">
                  {timeSeparatorLabel ? (
                    <div className="flex justify-center py-2">
                      <time className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
                        {timeSeparatorLabel}
                      </time>
                    </div>
                  ) : null}
                  <DocumentActivityFeedItem
                    item={item}
                    isClusteredWithPrevious={isClusteredWithPrevious}
                    isClusteredWithNext={isClusteredWithNext}
                    workspaceId={workspaceId}
                    currentUser={currentUser}
                    showDiscussions={showDiscussions}
                    activeReplyTargetKey={activeReplyTargetKey}
                    replyDraft={replyDraftsByTargetKey[item.replyTargetKey] ?? null}
                    submittingReplyTargetKey={submittingReplyTargetKey}
                    replyErrorTargetKey={replyErrorTargetKey}
                    activeEditCommentId={activeEditCommentId}
                    activeEditDraft={
                      activeEditCommentId ? (editDraftsByCommentId[activeEditCommentId] ?? null) : null
                    }
                    submittingEditCommentId={submittingEditCommentId}
                    editErrorCommentId={editErrorCommentId}
                    editErrorMessage={editErrorMessage}
                    onStartReply={onStartReply}
                    onCancelReply={onCancelReply}
                    onReplyDraftChange={onReplyDraftChange}
                    onSubmitReply={onSubmitReply}
                    onStartEdit={onStartEdit}
                    onCancelEdit={onCancelEdit}
                    onEditDraftChange={onEditDraftChange}
                    onSubmitEdit={onSubmitEdit}
                    onRequestDelete={(comment: ActivityComment) =>
                      setDeleteTarget({
                        commentId: comment.id,
                        authorName: comment.author?.name || comment.author?.email || "Unknown",
                        body: comment.body,
                      })
                    }
                  />
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete comment?"
        description="This permanently removes the comment from the document activity timeline."
        confirmLabel="Delete comment"
        cancelLabel="Cancel"
        tone="danger"
        isConfirming={isDeletingActiveTarget}
        onCancel={() => {
          if (!isDeletingActiveTarget) {
            setDeleteTarget(null);
          }
        }}
        onConfirm={() => {
          if (!deleteTarget) {
            return;
          }

          void onDeleteComment(deleteTarget.commentId)
            .then(() => {
              setDeleteTarget(null);
            })
            .catch(() => {
              // Keep the dialog open so the inline error remains visible.
            });
        }}
      >
        {deleteTarget ? (
          <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-2">
            <p className="text-sm font-medium text-foreground">{deleteTarget.authorName}</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
              {deleteTarget.body}
            </p>
          </div>
        ) : null}
        {deleteDialogError ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {deleteDialogError}
          </div>
        ) : null}
      </ConfirmDialog>
    </>
  );
}

function LoadingState() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-start gap-4">
          <Skeleton className="mt-1 size-8 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto max-w-3xl rounded-xl border border-border/70 bg-card/95 p-4 text-sm text-muted-foreground shadow-sm">
      No chat messages found for this filter.
    </div>
  );
}
