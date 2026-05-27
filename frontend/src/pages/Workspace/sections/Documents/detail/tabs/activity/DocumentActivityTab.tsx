import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentActivityComposer } from "./components/DocumentActivityComposer";
import { DocumentActivityFeed } from "./components/DocumentActivityFeed";
import { useDocumentActivityTimeline } from "./hooks/useDocumentActivityTimeline";
import { useDocumentActivityUiState } from "./hooks/useDocumentActivityUiState";
import { filterActivityItems } from "./model";

export function DocumentActivityTab({
  workspaceId,
  document,
}: {
  workspaceId: string;
  document: DocumentRow;
}) {
  const timeline = useDocumentActivityTimeline({
    workspaceId,
    document,
  });
  const ui = useDocumentActivityUiState({
    createNote: timeline.createNote,
    replyToItem: timeline.replyToItem,
    editComment: timeline.editComment,
  });
  const visibleItems = filterActivityItems(timeline.items, "all");
  const showDiscussions = true;

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-background">
      <DocumentActivityFeed
        workspaceId={workspaceId}
        currentUser={timeline.currentUser}
        items={visibleItems}
        isLoading={timeline.isLoading}
        hasError={timeline.hasError}
        showDiscussions={showDiscussions}
        activeReplyTargetKey={ui.activeReplyTarget?.targetKey ?? null}
        replyDraftsByTargetKey={ui.replyDraftsByTargetKey}
        submittingReplyTargetKey={timeline.replyingTargetKey}
        replyErrorTargetKey={ui.replyErrorTargetKey}
        activeEditCommentId={ui.activeEditCommentId}
        editDraftsByCommentId={ui.editDraftsByCommentId}
        submittingEditCommentId={timeline.editingCommentId}
        editErrorCommentId={ui.editErrorCommentId}
        editErrorMessage={ui.editErrorMessage}
        deletingCommentId={timeline.deletingCommentId}
        deleteErrorCommentId={timeline.deleteErrorCommentId}
        deleteErrorMessage={timeline.deleteErrorMessage}
        onStartReply={ui.startReply}
        onCancelReply={ui.cancelReply}
        onReplyDraftChange={ui.setReplyDraft}
        onSubmitReply={ui.submitReply}
        onStartEdit={ui.startEdit}
        onCancelEdit={ui.cancelEdit}
        onEditDraftChange={ui.setEditDraft}
        onSubmitEdit={ui.submitEdit}
        onDeleteComment={timeline.removeComment}
      />

      <DocumentActivityComposer
        workspaceId={workspaceId}
        isCreatingNote={timeline.isCreatingNote}
        noteError={ui.noteError}
        onCreateNote={ui.submitNote}
      />
    </div>
  );
}
