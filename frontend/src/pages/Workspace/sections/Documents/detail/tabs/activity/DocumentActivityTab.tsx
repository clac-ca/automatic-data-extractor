import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentActivityComposer } from "./components/DocumentActivityComposer";
import { DocumentActivityFeed } from "./components/DocumentActivityFeed";
import { DocumentActivityHeader } from "./components/DocumentActivityHeader";
import { useDocumentActivityTimeline } from "./hooks/useDocumentActivityTimeline";
import { useDocumentActivityUiState } from "./hooks/useDocumentActivityUiState";
import { filterActivityItems } from "./model";

export function DocumentActivityTab({
  workspaceId,
  document,
  filter,
  onFilterChange,
}: {
  workspaceId: string;
  document: DocumentRow;
  filter: DocumentActivityFilter;
  onFilterChange: (filter: DocumentActivityFilter) => void;
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
  const visibleItems = filterActivityItems(timeline.items, filter);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <DocumentActivityHeader
        filter={filter}
        onFilterChange={onFilterChange}
      />

      <DocumentActivityFeed
        workspaceId={workspaceId}
        currentUser={timeline.currentUser}
        items={visibleItems}
        isLoading={timeline.isLoading}
        hasError={timeline.hasError}
        activeReplyTargetKey={ui.activeReplyTarget?.targetKey ?? null}
        submittingReplyTargetKey={timeline.replyingTargetKey}
        replyErrorTargetKey={ui.replyErrorTargetKey}
        activeEditCommentId={ui.activeEditCommentId}
        submittingEditCommentId={timeline.editingCommentId}
        editErrorCommentId={ui.editErrorCommentId}
        editErrorMessage={ui.editErrorMessage}
        onStartReply={ui.startReply}
        onCancelReply={ui.cancelReply}
        onSubmitReply={ui.submitReply}
        onStartEdit={ui.startEdit}
        onCancelEdit={ui.cancelEdit}
        onSubmitEdit={ui.submitEdit}
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
