import { Separator } from "@/components/ui/separator";

import type { CommentDraft } from "../../comments/hooks/useDocumentComments";
import { CommentComposer } from "../../comments/components/CommentComposer";
import type { ActivityCurrentUser } from "../hooks/useDocumentActivityFeed";

export function DocumentActivityComposer({
  workspaceId,
  currentUser,
  isSubmitting,
  submitError,
  onSubmit,
}: {
  workspaceId: string;
  currentUser: ActivityCurrentUser;
  isSubmitting: boolean;
  submitError: string | null;
  onSubmit: (draft: CommentDraft) => void;
}) {
  return (
    <>
      <Separator />
      <div className="bg-background px-4 py-3">
        <CommentComposer
          workspaceId={workspaceId}
          currentUser={currentUser}
          onSubmit={onSubmit}
          isSubmitting={isSubmitting}
        />
        {submitError ? <div className="mt-2 text-xs text-destructive">{submitError}</div> : null}
      </div>
    </>
  );
}
