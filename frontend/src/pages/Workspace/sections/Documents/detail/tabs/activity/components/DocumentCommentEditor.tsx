import { useState } from "react";

import { CommentComposer, type CommentComposerDraft } from "../../comments/components/CommentComposer";
import { useCommentMentions } from "../hooks/useCommentMentions";
import type { ActivityComment } from "../model";
import type {
  CommentMentionDraft,
  NoteDraft,
} from "../activityTypes";

function toComposerDraft(comment?: ActivityComment | null): CommentComposerDraft | undefined {
  if (!comment) {
    return undefined;
  }

  return {
    body: comment.body,
    mentions: (comment.mentions ?? []).map((mention) => ({
      id: mention.user.id,
      name: mention.user.name ?? null,
      email: mention.user.email,
      start: mention.start,
      end: mention.end,
    })),
  };
}

function toDraft(draft: CommentComposerDraft): NoteDraft {
  return {
    body: draft.body,
    mentions: draft.mentions.map(
      (mention): CommentMentionDraft => ({
        user: {
          id: mention.id,
          name: mention.name ?? null,
          email: mention.email,
        },
        start: mention.start,
        end: mention.end,
      }),
    ),
  };
}

export function DocumentCommentEditor({
  workspaceId,
  mode,
  comment,
  variant = mode === "edit" ? "editing" : "compact",
  isSubmitting = false,
  errorMessage,
  onSubmit,
  onCancel,
  placeholder,
  helperText,
  autoFocus,
  showHeading,
}: {
  workspaceId: string;
  mode: "new" | "reply" | "edit";
  comment?: ActivityComment | null;
  variant?: "default" | "compact" | "editing";
  isSubmitting?: boolean;
  errorMessage?: string | null;
  onSubmit: (draft: NoteDraft) => Promise<unknown> | void;
  onCancel?: () => void;
  placeholder?: string;
  helperText?: string;
  autoFocus?: boolean;
  showHeading?: boolean;
}) {
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const { mentionSuggestions, isMentionLoading } = useCommentMentions(
    workspaceId,
    mentionQuery,
  );

  return (
    <div className="space-y-2">
      <CommentComposer
        mode={mode}
        variant={variant}
        initialDraft={toComposerDraft(comment)}
        mentionSuggestions={mentionSuggestions}
        isMentionLoading={isMentionLoading}
        onMentionQueryChange={setMentionQuery}
        isSubmitting={isSubmitting}
        onCancel={onCancel}
        onSubmit={(draft) => onSubmit(toDraft(draft))}
        placeholder={placeholder}
        helperText={helperText}
        autoFocus={autoFocus ?? mode !== "new"}
        showHeading={showHeading}
      />
      {errorMessage ? <div className="text-xs text-destructive">{errorMessage}</div> : null}
    </div>
  );
}
