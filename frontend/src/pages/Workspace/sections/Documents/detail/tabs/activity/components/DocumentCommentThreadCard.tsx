import { useMemo, type ReactNode } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { formatTimestamp } from "@/pages/Workspace/sections/Documents/shared/utils";

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
          "rounded px-1 text-xs font-semibold select-none transition-all duration-200",
          isCurrentUserMention
            ? "bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/20 scale-105 inline-block mx-0.5 font-bold"
            : "bg-primary/10 text-primary"
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

  const hasCurrentUserMention = useMemo(() => {
    return (comment.mentions ?? []).some((m) => m.user.id === currentUser.id);
  }, [comment.mentions, currentUser.id]);

  const highlightClass = isHighlighted
    ? "bg-amber-500/10 border-l-2 border-l-amber-500 px-3.5 py-2.5 -mx-3.5 rounded-r-md transition-all duration-700 animate-pulse-once"
    : hasCurrentUserMention
    ? "bg-amber-500/5 border-l-2 border-l-amber-500/40 px-3.5 py-2.5 -mx-3.5 rounded-r-md"
    : "";

  if (isEditing) {
    return (
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
    );
  }

  return (
    <div className={cn("group/comment flex items-start gap-3 transition-colors", comment.optimistic && "opacity-75", highlightClass)}>
      <Avatar className="mt-0.5 h-7 w-7 shrink-0">
        <AvatarFallback className="text-[11px] font-semibold">{buildInitials(authorName)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{authorName}</span>
              <span>{comment.optimistic ? "Sending..." : formatTimestamp(comment.createdAt)}</span>
              {isEditedComment(comment) ? (
                <Badge variant="outline" className="h-5 rounded-sm px-1.5 text-[10px] font-medium">
                  Edited
                </Badge>
              ) : null}
            </div>
          </div>
          {canManage ? (
            <div className="flex items-center gap-1 opacity-100 md:opacity-0 md:group-hover/comment:opacity-100 md:group-focus-within/comment:opacity-100">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[11px] text-muted-foreground"
                onClick={onEdit}
              >
                Edit
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[11px] text-muted-foreground"
                onClick={onRequestDelete}
              >
                Delete
              </Button>
            </div>
          ) : null}
        </div>
        <div className="mt-1.5 text-sm leading-6 text-foreground">{renderCommentBody(comment, currentUser.id)}</div>
      </div>
    </div>
  );
}

export function DocumentCommentThreadCard({
  variant,
  workspaceId,
  currentUser,
  thread,
  isReplyOpen,
  replyDraft,
  isReplySubmitting = false,
  replyErrorMessage,
  activeEditCommentId,
  activeEditDraft,
  submittingEditCommentId,
  editErrorCommentId,
  editErrorMessage,
  onStartReply,
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
        "overflow-hidden rounded-md border border-border/70 bg-background",
        variant === "attached" && "mt-2.5",
      )}
    >
      {comments.length > 0 ? (
        <div>
          {comments.map((comment, index) => (
            <div key={comment.id}>
              {index > 0 ? <Separator /> : null}
              <div className="px-3 py-2.5">
                <CommentRow
                  workspaceId={workspaceId}
                  comment={comment}
                  currentUser={currentUser}
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
            </div>
          ))}
        </div>
      ) : null}

      <div className={cn("px-3 py-2.5", comments.length > 0 && "border-t border-border/70")}>
        {isReplyOpen ? (
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
        ) : variant === "note" ? (
          <div className="flex items-center justify-end">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-xs text-muted-foreground"
              onClick={onStartReply}
            >
              Reply
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
