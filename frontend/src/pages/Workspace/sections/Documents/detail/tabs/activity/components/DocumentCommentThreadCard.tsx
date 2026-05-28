import type { ReactNode } from "react";
import { Pencil, Trash2 } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

import type {
  ActivityCurrentUser,
  CommentEditDraft,
  NoteDraft,
} from "../activityTypes";
import {
  buildInitials,
  type ActivityComment,
  type ActivityThread,
} from "../model";
import { DocumentCommentEditor } from "./DocumentCommentEditor";

function renderCommentBody(comment: ActivityComment, currentUserId?: string) {
  const mentions = [...(comment.mentions ?? [])].sort((left, right) => left.start - right.start);
  if (mentions.length === 0) {
    return <span className="whitespace-pre-wrap">{comment.body}</span>;
  }

  const nodes: ReactNode[] = [];
  let cursor = 0;

  mentions.forEach((mention) => {
    const safeStart = Math.max(cursor, mention.start);
    const safeEnd = Math.max(safeStart, mention.end);

    if (safeStart > cursor) {
      nodes.push(<span key={`text:${cursor}`}>{comment.body.slice(cursor, safeStart)}</span>);
    }

    const isCurrentUserMention = currentUserId && mention.user.id === currentUserId;

    nodes.push(
      <span
        key={`mention:${mention.user.id}:${safeStart}:${safeEnd}`}
        className={cn(
          "inline-block rounded border px-1 text-xs font-semibold select-none transition-all duration-200",
          isCurrentUserMention
            ? "border-primary/20 bg-primary/10 text-primary"
            : "border-border bg-muted text-foreground"
        )}
      >
        {comment.body.slice(safeStart, safeEnd)}
      </span>,
    );

    cursor = safeEnd;
  });

  if (cursor < comment.body.length) {
    nodes.push(<span key={`text:${cursor}`}>{comment.body.slice(cursor)}</span>);
  }

  return <span className="whitespace-pre-wrap">{nodes}</span>;
}

function isEditedComment(comment: ActivityComment) {
  if (!comment.editedAt) {
    return false;
  }

  const createdAt = new Date(comment.createdAt).getTime();
  const editedAt = new Date(comment.editedAt).getTime();

  if (Number.isNaN(createdAt) || Number.isNaN(editedAt)) {
    return false;
  }

  return editedAt > createdAt;
}

function CommentRow({
  workspaceId,
  comment,
  currentUser,
  isClustered,
  isLastInCluster,
  isEditing,
  editDraft,
  isSubmittingEdit,
  editErrorMessage,
  onEdit,
  onRequestDelete,
  onSubmitEdit,
  onEditDraftChange,
  onCancelEdit,
}: {
  workspaceId: string;
  comment: ActivityComment;
  currentUser: ActivityCurrentUser;
  isClustered: boolean;
  isLastInCluster: boolean;
  isEditing: boolean;
  editDraft?: NoteDraft | null;
  isSubmittingEdit: boolean;
  editErrorMessage?: string | null;
  onEdit: () => void;
  onRequestDelete: () => void;
  onSubmitEdit: (draft: CommentEditDraft) => Promise<unknown> | void;
  onEditDraftChange: (draft: NoteDraft) => void;
  onCancelEdit: () => void;
}) {
  const authorName = comment.author?.name || comment.author?.email || "Unknown";
  const canManage = comment.author?.id === currentUser.id && !comment.optimistic;

  const highlightCommentId = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("highlightCommentId")
    : null;
  const isHighlighted = highlightCommentId === comment.id;

  const bubbleHighlightClass = isHighlighted
    ? "border-amber-500/60 bg-amber-500/10 ring-1 ring-amber-500/30 transition-all duration-700 animate-pulse-once"
    : "";
  const isOwnMessage = comment.author?.id === currentUser.id;
  const showAvatar = isLastInCluster;
  const showMeta = !isClustered && !isOwnMessage;

  if (isEditing) {
    return (
      <div className={cn("flex items-start gap-3", isOwnMessage && "justify-end")}>
        {!isOwnMessage ? (
          <Avatar className="mt-0.5 size-8 shrink-0 border border-border/70 bg-card shadow-sm">
            <AvatarFallback className="bg-card text-[11px] font-semibold text-foreground">
              {buildInitials(authorName)}
            </AvatarFallback>
          </Avatar>
        ) : null}
        <div className="w-full max-w-[44rem] rounded-xl border border-border/70 bg-card p-2 shadow-sm">
          <DocumentCommentEditor
            workspaceId={workspaceId}
            mode="edit"
            comment={comment}
            draft={editDraft}
            variant="editing"
            isSubmitting={isSubmittingEdit}
            errorMessage={editErrorMessage}
            onDraftChange={onEditDraftChange}
            onCancel={onCancelEdit}
            onSubmit={(draft) =>
              onSubmitEdit({
                commentId: comment.id,
                body: draft.body,
                mentions: draft.mentions,
              })
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group/comment flex items-end gap-2 transition-colors",
        isOwnMessage && "justify-end",
        comment.optimistic && "opacity-75",
      )}
    >
      {!isOwnMessage && showAvatar ? (
        <Avatar className="mb-0.5 size-8 shrink-0 border border-border/70 bg-card shadow-sm">
          <AvatarFallback className="bg-card text-[11px] font-semibold text-foreground">
            {buildInitials(authorName)}
          </AvatarFallback>
        </Avatar>
      ) : null}
      {!isOwnMessage && !showAvatar ? <div className="size-8 shrink-0" /> : null}
      <div className={cn("min-w-0 flex max-w-[min(42rem,76%)] flex-col gap-0.5", isOwnMessage && "items-end")}>
        {showMeta ? (
          <div className="flex items-center gap-2 px-1">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{authorName}</span>
                {isEditedComment(comment) ? (
                  <Badge variant="outline" className="h-5 rounded-sm px-1.5 text-[10px] font-medium">
                    Edited
                  </Badge>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
        <div className={cn("flex items-center gap-1", isOwnMessage && "flex-row-reverse")}>
          <div
            className={cn(
              "break-words rounded-2xl border px-4 py-2.5 text-sm leading-6 shadow-sm transition-shadow group-hover/comment:shadow-md",
              isOwnMessage
                ? "rounded-br-md border-primary/15 bg-primary/5 text-foreground"
                : "rounded-bl-md border-border/70 bg-card text-foreground",
              isClustered && isOwnMessage && "rounded-tr-md",
              isClustered && !isOwnMessage && "rounded-tl-md",
              !isLastInCluster && isOwnMessage && "rounded-br-md",
              !isLastInCluster && !isOwnMessage && "rounded-bl-md",
              bubbleHighlightClass,
            )}
          >
            {renderCommentBody(comment, currentUser.id)}
          </div>
          {canManage ? (
            <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover/comment:opacity-100 group-focus-within/comment:opacity-100">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 rounded-full text-muted-foreground"
                onClick={onEdit}
                aria-label="Edit"
                title="Edit"
              >
                <Pencil data-icon="inline-start" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 rounded-full text-muted-foreground"
                onClick={onRequestDelete}
                aria-label="Delete"
                title="Delete"
              >
                <Trash2 data-icon="inline-start" />
              </Button>
            </div>
          ) : null}
        </div>
      </div>
      {isOwnMessage && showAvatar ? (
        <Avatar className="mb-0.5 size-7 shrink-0 border border-primary/20 bg-primary/5 shadow-sm">
          <AvatarFallback className="bg-primary/5 text-[10px] font-semibold text-foreground">
            {buildInitials(authorName)}
          </AvatarFallback>
        </Avatar>
      ) : null}
      {isOwnMessage && !showAvatar ? <div className="size-7 shrink-0" /> : null}
    </div>
  );
}

function isSameAuthor(left: ActivityComment, right: ActivityComment) {
  const leftAuthor = left.author?.id ?? left.author?.email ?? null;
  const rightAuthor = right.author?.id ?? right.author?.email ?? null;
  return Boolean(leftAuthor && rightAuthor && leftAuthor === rightAuthor);
}

function isCloseInTime(left: ActivityComment, right: ActivityComment) {
  const leftTime = new Date(left.createdAt).getTime();
  const rightTime = new Date(right.createdAt).getTime();

  if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
    return false;
  }

  return Math.abs(rightTime - leftTime) <= 15 * 60 * 1000;
}

export function DocumentCommentThreadCard({
  variant,
  workspaceId,
  currentUser,
  thread,
  clusterWithPrevious = false,
  clusterWithNext = false,
  isReplyOpen,
  replyDraft,
  isReplySubmitting = false,
  replyErrorMessage,
  activeEditCommentId,
  activeEditDraft,
  submittingEditCommentId,
  editErrorCommentId,
  editErrorMessage,
  onCancelReply,
  onReplyDraftChange,
  onSubmitReply,
  onStartEdit,
  onCancelEdit,
  onEditDraftChange,
  onSubmitEdit,
  onRequestDelete,
}: {
  variant: "note" | "attached";
  workspaceId: string;
  currentUser: ActivityCurrentUser;
  thread: ActivityThread | null;
  clusterWithPrevious?: boolean;
  clusterWithNext?: boolean;
  isReplyOpen: boolean;
  replyDraft?: NoteDraft | null;
  isReplySubmitting?: boolean;
  replyErrorMessage?: string | null;
  activeEditCommentId: string | null;
  activeEditDraft?: NoteDraft | null;
  submittingEditCommentId: string | null;
  editErrorCommentId: string | null;
  editErrorMessage?: string | null;
  onStartReply: () => void;
  onCancelReply: () => void;
  onReplyDraftChange: (draft: NoteDraft) => void;
  onSubmitReply: (draft: NoteDraft) => Promise<unknown> | void;
  onStartEdit: (commentId: string) => void;
  onCancelEdit: () => void;
  onEditDraftChange: (commentId: string, draft: NoteDraft) => void;
  onSubmitEdit: (draft: CommentEditDraft) => Promise<unknown> | void;
  onRequestDelete: (comment: ActivityComment) => void;
}) {
  const comments = thread?.comments ?? [];

  if (comments.length === 0 && !isReplyOpen) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-1.5",
        variant === "attached" && "mx-auto max-w-[92%]",
      )}
    >
      {comments.length > 0 ? (
        <div className="flex flex-col gap-0.5">
          {comments.map((comment, index) => {
            const previousComment = comments[index - 1];
            const nextComment = comments[index + 1];
            const isClustered =
              (Boolean(previousComment) &&
                isSameAuthor(previousComment, comment) &&
                isCloseInTime(previousComment, comment)) ||
              (index === 0 && clusterWithPrevious);
            const isLastInCluster =
              !(
                (nextComment && isSameAuthor(comment, nextComment) && isCloseInTime(comment, nextComment)) ||
                (index === comments.length - 1 && clusterWithNext)
              );

            return (
              <div key={comment.id}>
                {variant === "attached" && index === 0 ? <Separator className="mb-3" /> : null}
                <CommentRow
                  workspaceId={workspaceId}
                  comment={comment}
                  currentUser={currentUser}
                  isClustered={isClustered}
                  isLastInCluster={isLastInCluster}
                  isEditing={activeEditCommentId === comment.id}
                  editDraft={activeEditCommentId === comment.id ? activeEditDraft : null}
                  isSubmittingEdit={submittingEditCommentId === comment.id}
                  editErrorMessage={editErrorCommentId === comment.id ? editErrorMessage : null}
                  onEdit={() => onStartEdit(comment.id)}
                  onRequestDelete={() => onRequestDelete(comment)}
                  onEditDraftChange={(draft) => onEditDraftChange(comment.id, draft)}
                  onCancelEdit={onCancelEdit}
                  onSubmitEdit={onSubmitEdit}
                />
              </div>
            );
          })}
        </div>
      ) : null}

      <div>
        {isReplyOpen ? (
          <div className="ml-11 max-w-[72%] rounded-xl border border-border/70 bg-card p-2 shadow-sm">
            <DocumentCommentEditor
              workspaceId={workspaceId}
              mode="reply"
              draft={replyDraft}
              variant="compact"
              isSubmitting={isReplySubmitting}
              errorMessage={replyErrorMessage}
              onDraftChange={onReplyDraftChange}
              onCancel={onCancelReply}
              onSubmit={onSubmitReply}
              placeholder={variant === "note" ? "Reply to this note..." : "Reply to this activity..."}
              helperText="Use @ to mention someone. Enter sends, Shift+Enter adds a new line."
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
