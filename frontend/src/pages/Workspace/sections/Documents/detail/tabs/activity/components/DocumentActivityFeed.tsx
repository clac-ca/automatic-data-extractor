import { Timeline } from "@/components/ui/timeline";
import { Skeleton } from "@/components/ui/skeleton";

import type {
  ActivityCurrentUser,
  ActivityReplyTarget,
  CommentEditDraft,
  NoteDraft,
  ThreadReplyDraft,
} from "../activityTypes";
import type { ActivityItem } from "../model";
import { DocumentActivityFeedItem } from "./DocumentActivityFeedItem";

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
  onStartReply,
  onCancelReply,
  onReplyDraftChange,
  onSubmitReply,
  onStartEdit,
  onCancelEdit,
  onEditDraftChange,
  onSubmitEdit,
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
  onStartReply: (target: ActivityReplyTarget) => void;
  onCancelReply: () => void;
  onReplyDraftChange: (targetKey: string, draft: NoteDraft) => void;
  onSubmitReply: (draft: ThreadReplyDraft) => Promise<unknown> | void;
  onStartEdit: (commentId: string) => void;
  onCancelEdit: () => void;
  onEditDraftChange: (commentId: string, draft: NoteDraft) => void;
  onSubmitEdit: (draft: CommentEditDraft) => Promise<unknown> | void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-auto px-4 py-3">
      {hasError && !isLoading ? (
        <div className="mb-4 rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
          Activity could not be fully loaded right now.
        </div>
      ) : null}

      {isLoading ? <LoadingState /> : null}
      {!isLoading && items.length === 0 ? <EmptyState /> : null}
      {!isLoading && items.length > 0 ? (
        <Timeline className="gap-4">
          {items.map((item) => (
            <DocumentActivityFeedItem
              key={item.key}
              item={item}
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
            />
          ))}
        </Timeline>
      ) : null}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-start gap-4">
          <Skeleton className="mt-1 h-4 w-4 rounded-full" />
          <div className="flex-1 space-y-2">
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
    <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
      No activity found for this filter.
    </div>
  );
}
