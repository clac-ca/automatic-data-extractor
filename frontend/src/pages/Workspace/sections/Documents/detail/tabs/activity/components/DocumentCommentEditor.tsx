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

function toComposerDraftFromNote(draft?: NoteDraft | null): CommentComposerDraft | undefined {
  if (!draft) {
    return undefined;
  }

  return {
    body: draft.body,
    mentions: draft.mentions.map((mention) => ({
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
  draft,
  variant = mode === "edit" ? "editing" : "compact",
  isSubmitting = false,
  errorMessage,
  onSubmit,
  onDraftChange,
  onCancel,
  placeholder,
  helperText,
  shouldAutoFocus,
  showHeading,
}: {
  workspaceId: string;
  mode: "new" | "reply" | "edit";
  comment?: ActivityComment | null;
  draft?: NoteDraft | null;
  variant?: "default" | "compact" | "editing";
  isSubmitting?: boolean;
  errorMessage?: string | null;
  onSubmit: (draft: NoteDraft) => Promise<unknown> | void;
  onDraftChange?: (draft: NoteDraft) => void;
  onCancel?: () => void;
  placeholder?: string;
  helperText?: string;
  shouldAutoFocus?: boolean;
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
        draft={toComposerDraftFromNote(draft)}
        onDraftChange={onDraftChange ? (nextDraft) => onDraftChange(toDraft(nextDraft)) : undefined}
        mentionSuggestions={mentionSuggestions}
        isMentionLoading={isMentionLoading}
        onMentionQueryChange={setMentionQuery}
        isSubmitting={isSubmitting}
        onCancel={onCancel}
        onSubmit={(draft) => onSubmit(toDraft(draft))}
        placeholder={placeholder}
        helperText={helperText}
        shouldAutoFocus={shouldAutoFocus ?? mode !== "new"}
        showHeading={showHeading}
      />
      {errorMessage ? <div className="text-xs text-destructive">{errorMessage}</div> : null}
    </div>
  );
}
