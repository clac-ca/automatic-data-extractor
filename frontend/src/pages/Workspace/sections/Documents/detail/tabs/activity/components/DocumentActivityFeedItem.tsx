import type { ReactNode } from "react";
import { PlayCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  shortId,
} from "@/pages/Workspace/sections/Documents/shared/utils";
import type { RunStatus } from "@/types";

import type {
  ActivityCurrentUser,
  ActivityReplyTarget,
  CommentEditDraft,
  NoteDraft,
  ThreadReplyDraft,
} from "../activityTypes";
import {
  ACTIVITY_ICON,
  formatRunStatus,
  RUN_TONE,
  type ActivityComment,
  type ActivityItem,
} from "../model";
import { DocumentCommentThreadCard } from "./DocumentCommentThreadCard";

function ActivityEventShell({
  item,
  icon,
  iconClassName,
  title,
  description,
  children,
}: {
  item: Extract<ActivityItem, { type: "document" | "run" }>;
  icon: ReactNode;
  iconClassName?: string;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div id={item.key} className="flex flex-col items-center gap-3">
      <div className="group/event flex max-w-full items-center gap-3 rounded-full border border-border/70 bg-card px-3 py-2 text-xs text-muted-foreground shadow-sm">
        <span className={cn("flex size-7 items-center justify-center rounded-full border bg-background", iconClassName)}>
          {icon}
        </span>
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="truncate font-medium text-foreground">{title}</span>
          {description ? (
            <span className="truncate text-muted-foreground">{description}</span>
          ) : null}
        </div>
      </div>
      {children ? <div className="w-full">{children}</div> : null}
    </div>
  );
}

function RunDescription({ item }: { item: Extract<ActivityItem, { type: "run" }> }) {
  const hasDuration = item.run.durationSeconds !== null && item.run.durationSeconds !== undefined;

  return (
    <span>
      {hasDuration ? (
        <span>
          Duration <span className="font-medium text-foreground">{Math.round(item.run.durationSeconds ?? 0)}s</span>
        </span>
      ) : null}
      {item.run.errorMessage ? <span className="text-destructive">{item.run.errorMessage}</span> : null}
      {!hasDuration && !item.run.errorMessage ? <span>{formatRunStatus(String(item.run.status))}</span> : null}
    </span>
  );
}

function buildReplyTarget(item: ActivityItem): ActivityReplyTarget {
  if (item.type === "note") {
    return {
      targetKey: item.replyTargetKey,
      threadId: item.thread.id,
    };
  }

  return {
    targetKey: item.replyTargetKey,
    threadId: item.thread?.id ?? null,
    anchorType: item.type,
    anchorId: item.id,
  };
}

export function DocumentActivityFeedItem({
  item,
  isClusteredWithPrevious = false,
  isClusteredWithNext = false,
  workspaceId,
  currentUser,
  showDiscussions,
  activeReplyTargetKey,
  replyDraft,
  submittingReplyTargetKey,
  replyErrorTargetKey,
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
  item: ActivityItem;
  isClusteredWithPrevious?: boolean;
  isClusteredWithNext?: boolean;
  workspaceId: string;
  currentUser: ActivityCurrentUser;
  showDiscussions: boolean;
  activeReplyTargetKey: string | null;
  replyDraft?: NoteDraft | null;
  submittingReplyTargetKey: string | null;
  replyErrorTargetKey: string | null;
  activeEditCommentId: string | null;
  activeEditDraft?: NoteDraft | null;
  submittingEditCommentId: string | null;
  editErrorCommentId: string | null;
  editErrorMessage?: string | null;
  onStartReply: (target: ActivityReplyTarget) => void;
  onCancelReply: () => void;
  onReplyDraftChange: (targetKey: string, draft: NoteDraft) => void;
  onSubmitReply: (draft: ThreadReplyDraft) => Promise<unknown> | void;
  onStartEdit: (commentId: string) => void;
  onCancelEdit: () => void;
  onEditDraftChange: (commentId: string, draft: NoteDraft) => void;
  onSubmitEdit: (draft: CommentEditDraft) => Promise<unknown> | void;
  onRequestDelete: (comment: ActivityComment) => void;
}) {
  const replyTarget = buildReplyTarget(item);
  const isReplyOpen = activeReplyTargetKey === item.replyTargetKey;
  const replyErrorMessage =
    replyErrorTargetKey === item.replyTargetKey ? "Unable to send reply right now." : null;

  if (item.type === "note") {
    return (
      <div className={cn(isClusteredWithPrevious && "-mt-3.5")}>
        <DocumentCommentThreadCard
          variant="note"
          workspaceId={workspaceId}
          currentUser={currentUser}
          thread={item.thread}
          clusterWithPrevious={isClusteredWithPrevious}
          clusterWithNext={isClusteredWithNext}
          isReplyOpen={isReplyOpen}
          replyDraft={replyDraft}
          isReplySubmitting={submittingReplyTargetKey === item.replyTargetKey}
          replyErrorMessage={replyErrorMessage}
          activeEditCommentId={activeEditCommentId}
          activeEditDraft={activeEditDraft}
          submittingEditCommentId={submittingEditCommentId}
          editErrorCommentId={editErrorCommentId}
          editErrorMessage={editErrorMessage}
          onStartReply={() => onStartReply(replyTarget)}
          onCancelReply={onCancelReply}
          onReplyDraftChange={(draft) => onReplyDraftChange(item.replyTargetKey, draft)}
          onSubmitReply={(draft: NoteDraft) =>
            onSubmitReply({
              targetKey: item.replyTargetKey,
              threadId: item.thread.id,
              body: draft.body,
              mentions: draft.mentions,
            })
          }
          onStartEdit={onStartEdit}
          onCancelEdit={onCancelEdit}
          onEditDraftChange={onEditDraftChange}
          onSubmitEdit={onSubmitEdit}
          onRequestDelete={onRequestDelete}
        />
      </div>
    );
  }

  if (item.type === "document") {
    const uploaderName = item.uploader?.name || item.uploader?.email || "Unknown";
    return (
      <ActivityEventShell
        item={item}
        icon={<ACTIVITY_ICON.document className="h-4 w-4" />}
        iconClassName="border-primary/40 bg-primary/5 text-primary"
        title="Document uploaded"
        description={
          <span>
            Uploaded by <span className="font-medium text-foreground">{uploaderName}</span>
          </span>
        }
      >
        {showDiscussions && (item.thread || isReplyOpen) ? (
          <DocumentCommentThreadCard
            variant="attached"
            workspaceId={workspaceId}
            currentUser={currentUser}
            thread={item.thread}
            isReplyOpen={isReplyOpen}
            replyDraft={replyDraft}
            isReplySubmitting={submittingReplyTargetKey === item.replyTargetKey}
            replyErrorMessage={replyErrorMessage}
            activeEditCommentId={activeEditCommentId}
            activeEditDraft={activeEditDraft}
            submittingEditCommentId={submittingEditCommentId}
            editErrorCommentId={editErrorCommentId}
            editErrorMessage={editErrorMessage}
            onStartReply={() => onStartReply(replyTarget)}
            onCancelReply={onCancelReply}
            onReplyDraftChange={(draft) => onReplyDraftChange(item.replyTargetKey, draft)}
            onSubmitReply={(draft: NoteDraft) =>
              onSubmitReply({
                targetKey: item.replyTargetKey,
                threadId: item.thread?.id ?? undefined,
                anchorType: "document",
                anchorId: item.id,
                body: draft.body,
                mentions: draft.mentions,
              })
            }
            onStartEdit={onStartEdit}
            onCancelEdit={onCancelEdit}
            onEditDraftChange={onEditDraftChange}
            onSubmitEdit={onSubmitEdit}
            onRequestDelete={onRequestDelete}
          />
        ) : null}
      </ActivityEventShell>
    );
  }

  const status = item.run.status as RunStatus;
  const tone = RUN_TONE[status];
  const DotIcon = tone?.Icon ?? PlayCircle;

  return (
    <ActivityEventShell
      item={item}
      icon={<DotIcon className="h-4 w-4" />}
      iconClassName={cn("border-border bg-muted/30 text-muted-foreground", tone?.dot)}
      title={<span className="font-mono">Run {shortId(item.run.id)}</span>}
      description={<RunDescription item={item} />}
    >
      {showDiscussions && (item.thread || isReplyOpen) ? (
        <DocumentCommentThreadCard
          variant="attached"
          workspaceId={workspaceId}
          currentUser={currentUser}
          thread={item.thread}
          isReplyOpen={isReplyOpen}
          replyDraft={replyDraft}
          isReplySubmitting={submittingReplyTargetKey === item.replyTargetKey}
          replyErrorMessage={replyErrorMessage}
          activeEditCommentId={activeEditCommentId}
          activeEditDraft={activeEditDraft}
          submittingEditCommentId={submittingEditCommentId}
          editErrorCommentId={editErrorCommentId}
          editErrorMessage={editErrorMessage}
          onStartReply={() => onStartReply(replyTarget)}
          onCancelReply={onCancelReply}
          onReplyDraftChange={(draft) => onReplyDraftChange(item.replyTargetKey, draft)}
          onSubmitReply={(draft: NoteDraft) =>
            onSubmitReply({
              targetKey: item.replyTargetKey,
              threadId: item.thread?.id ?? undefined,
              anchorType: "run",
              anchorId: item.id,
              body: draft.body,
              mentions: draft.mentions,
            })
          }
          onStartEdit={onStartEdit}
          onCancelEdit={onCancelEdit}
          onEditDraftChange={onEditDraftChange}
          onSubmitEdit={onSubmitEdit}
          onRequestDelete={onRequestDelete}
        />
      ) : null}
    </ActivityEventShell>
  );
}
