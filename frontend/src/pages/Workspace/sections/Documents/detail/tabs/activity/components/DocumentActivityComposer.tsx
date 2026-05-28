import type { NoteDraft } from "../activityTypes";
import { DocumentCommentEditor } from "./DocumentCommentEditor";

export function DocumentActivityComposer({
  workspaceId,
  isCreatingNote,
  noteError,
  onCreateNote,
}: {
  workspaceId: string;
  isCreatingNote: boolean;
  noteError: string | null;
  onCreateNote: (draft: NoteDraft) => Promise<void>;
}) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 px-4 pb-3 pt-8">
      <div className="pointer-events-auto mx-auto max-w-4xl rounded-xl border border-border/70 bg-card p-2 shadow-sm">
        <DocumentCommentEditor
          workspaceId={workspaceId}
          mode="new"
          variant="compact"
          isSubmitting={isCreatingNote}
          errorMessage={noteError}
          placeholder="Add a comment..."
          helperText="Use @ to mention someone. Enter sends, Shift+Enter adds a new line."
          showHeading={false}
          expandOnFocus={false}
          onSubmit={onCreateNote}
        />
      </div>
    </div>
  );
}
