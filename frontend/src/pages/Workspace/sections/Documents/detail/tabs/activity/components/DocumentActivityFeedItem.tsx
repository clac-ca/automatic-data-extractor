import type { ReactNode } from "react";
import { PlayCircle } from "lucide-react";

import {
  TimelineConnector,
  TimelineContent,
  TimelineDescription,
  TimelineDot,
  TimelineItem,
  TimelineTime,
  TimelineTitle,
} from "@/components/ui/timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  formatTimestamp,
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
  type ActivityItem,
} from "../model";
import { DocumentCommentThreadCard } from "./DocumentCommentThreadCard";

function ActivityEventShell({
  item,
  icon,
  iconClassName,
  title,
  description,
  isReplyOpen,
  onReplyToggle,
  children,
}: {
  item: Extract<ActivityItem, { type: "document" | "run" }>;
  icon: ReactNode;
  iconClassName?: string;
  title: ReactNode;
  description?: ReactNode;
  isReplyOpen: boolean;
  onReplyToggle: () => void;
  children?: ReactNode;
}) {
  return (
    <TimelineItem id={item.key} className="gap-3">
      <TimelineDot className={cn("mt-1 flex items-center justify-center", iconClassName)}>{icon}</TimelineDot>
      <TimelineConnector />
      <TimelineContent className="space-y-3 pb-2">
        <div className="group/event flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <TimelineTitle className="text-sm text-foreground">{title}</TimelineTitle>
            {description ? (
              <TimelineDescription className="text-xs leading-5">{description}</TimelineDescription>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <TimelineTime dateTime={item.activityAt}>{formatTimestamp(item.activityAt)}</TimelineTime>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground"
              onClick={onReplyToggle}
            >
              {isReplyOpen ? "Cancel" : "Reply"}
            </Button>
          </div>
        </div>
        {children}
      </TimelineContent>
    </TimelineItem>
  );
}

function RunDescription({ item }: { item: Extract<ActivityItem, { type: "run" }> }) {
  const hasDuration = item.run.durationSeconds !== null && item.run.durationSeconds !== undefined;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {hasDuration ? (
        <span>
          Duration <span className="font-medium text-foreground">{Math.round(item.run.durationSeconds ?? 0)}s</span>
        </span>
      ) : null}
      {item.run.exitCode !== null && item.run.exitCode !== undefined ? <span>Exit {item.run.exitCode}</span> : null}
      {item.run.errorMessage ? <span className="text-destructive">{item.run.errorMessage}</span> : null}
      {!hasDuration && item.run.exitCode === null && !item.run.errorMessage ? (
        <span>Status: {formatRunStatus(String(item.run.status))}</span>
      ) : null}
    </div>
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
  workspaceId,
  currentUser,
  activeReplyTargetKey,
  submittingReplyTargetKey,
  replyErrorTargetKey,
  activeEditCommentId,
  submittingEditCommentId,
  editErrorCommentId,
  editErrorMessage,
  onStartReply,
  onCancelReply,
  onSubmitReply,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
}: {
  item: ActivityItem;
  workspaceId: string;
  currentUser: ActivityCurrentUser;
  activeReplyTargetKey: string | null;
  submittingReplyTargetKey: string | null;
  replyErrorTargetKey: string | null;
  activeEditCommentId: string | null;
  submittingEditCommentId: string | null;
  editErrorCommentId: string | null;
  editErrorMessage?: string | null;
  onStartReply: (target: ActivityReplyTarget) => void;
  onCancelReply: () => void;
  onSubmitReply: (draft: ThreadReplyDraft) => Promise<unknown> | void;
  onStartEdit: (commentId: string) => void;
  onCancelEdit: () => void;
  onSubmitEdit: (draft: CommentEditDraft) => Promise<unknown> | void;
}) {
  const replyTarget = buildReplyTarget(item);
  const isReplyOpen = activeReplyTargetKey === item.replyTargetKey;
  const replyErrorMessage =
    replyErrorTargetKey === item.replyTargetKey ? "Unable to send reply right now." : null;

  if (item.type === "note") {
    return (
      <TimelineItem id={item.key} className="gap-3">
        <TimelineDot className="mt-1 border-primary/40 bg-primary/5 text-primary">
          <ACTIVITY_ICON.note className="h-4 w-4" />
        </TimelineDot>
        <TimelineConnector />
        <TimelineContent className="pb-2">
          <DocumentCommentThreadCard
            variant="note"
            workspaceId={workspaceId}
            currentUser={currentUser}
            thread={item.thread}
            isReplyOpen={isReplyOpen}
            isReplySubmitting={submittingReplyTargetKey === item.replyTargetKey}
            replyErrorMessage={replyErrorMessage}
            activeEditCommentId={activeEditCommentId}
            submittingEditCommentId={submittingEditCommentId}
            editErrorCommentId={editErrorCommentId}
            editErrorMessage={editErrorMessage}
            onStartReply={() => onStartReply(replyTarget)}
            onCancelReply={onCancelReply}
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
            onSubmitEdit={onSubmitEdit}
          />
        </TimelineContent>
      </TimelineItem>
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
        isReplyOpen={isReplyOpen}
        onReplyToggle={() => (isReplyOpen ? onCancelReply() : onStartReply(replyTarget))}
      >
        {(item.thread || isReplyOpen) ? (
          <DocumentCommentThreadCard
            variant="attached"
            workspaceId={workspaceId}
            currentUser={currentUser}
            thread={item.thread}
            isReplyOpen={isReplyOpen}
            isReplySubmitting={submittingReplyTargetKey === item.replyTargetKey}
            replyErrorMessage={replyErrorMessage}
            activeEditCommentId={activeEditCommentId}
            submittingEditCommentId={submittingEditCommentId}
            editErrorCommentId={editErrorCommentId}
            editErrorMessage={editErrorMessage}
            onStartReply={() => onStartReply(replyTarget)}
            onCancelReply={onCancelReply}
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
            onSubmitEdit={onSubmitEdit}
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
      title={
        <div className="flex items-center gap-2">
          <span className="font-mono">Run {shortId(item.run.id)}</span>
          <Badge variant="outline" className={cn("capitalize", tone?.badge)}>
            {formatRunStatus(String(item.run.status))}
          </Badge>
        </div>
      }
      description={<RunDescription item={item} />}
      isReplyOpen={isReplyOpen}
      onReplyToggle={() => (isReplyOpen ? onCancelReply() : onStartReply(replyTarget))}
    >
      {(item.thread || isReplyOpen) ? (
        <DocumentCommentThreadCard
          variant="attached"
          workspaceId={workspaceId}
          currentUser={currentUser}
          thread={item.thread}
          isReplyOpen={isReplyOpen}
          isReplySubmitting={submittingReplyTargetKey === item.replyTargetKey}
          replyErrorMessage={replyErrorMessage}
          activeEditCommentId={activeEditCommentId}
          submittingEditCommentId={submittingEditCommentId}
          editErrorCommentId={editErrorCommentId}
          editErrorMessage={editErrorMessage}
          onStartReply={() => onStartReply(replyTarget)}
          onCancelReply={onCancelReply}
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
          onSubmitEdit={onSubmitEdit}
        />
      ) : null}
    </ActivityEventShell>
  );
}
