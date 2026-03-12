import { Separator } from "@/components/ui/separator";

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
    <>
      <Separator />
      <div className="bg-background px-4 py-2.5">
        <DocumentCommentEditor
          workspaceId={workspaceId}
          mode="new"
          variant="compact"
          isSubmitting={isCreatingNote}
          errorMessage={noteError}
          placeholder="Add a note, decision, or request..."
          helperText="Add a note to the timeline. Enter sends, Shift+Enter adds a new line."
          showHeading={false}
          onSubmit={onCreateNote}
        />
      </div>
    </>
  );
}
