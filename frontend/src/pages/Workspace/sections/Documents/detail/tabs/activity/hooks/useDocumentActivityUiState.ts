import { useCallback, useState } from "react";

import type {
  ActivityReplyTarget,
  CommentEditDraft,
  NoteDraft,
  ThreadReplyDraft,
} from "../activityTypes";

function toMutationMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unable to save that message right now.";
}

export function useDocumentActivityUiState({
  createNote,
  replyToItem,
  editComment,
}: {
  createNote: (draft: NoteDraft) => Promise<void>;
  replyToItem: (draft: ThreadReplyDraft) => Promise<void>;
  editComment: (draft: CommentEditDraft) => Promise<void>;
}) {
  const [activeReplyTarget, setActiveReplyTarget] = useState<ActivityReplyTarget | null>(null);
  const [activeEditCommentId, setActiveEditCommentId] = useState<string | null>(null);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [replyErrorTargetKey, setReplyErrorTargetKey] = useState<string | null>(null);
  const [editErrorCommentId, setEditErrorCommentId] = useState<string | null>(null);
  const [editErrorMessage, setEditErrorMessage] = useState<string | null>(null);
  const [replyDraftsByTargetKey, setReplyDraftsByTargetKey] = useState<Record<string, NoteDraft>>({});
  const [editDraftsByCommentId, setEditDraftsByCommentId] = useState<Record<string, NoteDraft>>({});

  const startReply = useCallback((target: ActivityReplyTarget) => {
    setNoteError(null);
    setActiveEditCommentId(null);
    setEditErrorCommentId(null);
    setEditErrorMessage(null);
    setReplyErrorTargetKey(null);
    setActiveReplyTarget(target);
  }, []);

  const cancelReply = useCallback(() => {
    setNoteError(null);
    setReplyErrorTargetKey(null);
    setReplyDraftsByTargetKey((current) => {
      if (!activeReplyTarget?.targetKey) {
        return current;
      }

      const { [activeReplyTarget.targetKey]: _discarded, ...rest } = current;
      return rest;
    });
    setActiveReplyTarget(null);
  }, [activeReplyTarget?.targetKey]);

  const startEdit = useCallback((commentId: string) => {
    setNoteError(null);
    setActiveReplyTarget(null);
    setReplyErrorTargetKey(null);
    setEditErrorCommentId(null);
    setEditErrorMessage(null);
    setActiveEditCommentId(commentId);
  }, []);

  const cancelEdit = useCallback(() => {
    setNoteError(null);
    setEditErrorCommentId(null);
    setEditErrorMessage(null);
    setEditDraftsByCommentId((current) => {
      if (!activeEditCommentId) {
        return current;
      }

      const { [activeEditCommentId]: _discarded, ...rest } = current;
      return rest;
    });
    setActiveEditCommentId(null);
  }, [activeEditCommentId]);

  const setReplyDraft = useCallback((targetKey: string, draft: NoteDraft) => {
    setReplyDraftsByTargetKey((current) => ({
      ...current,
      [targetKey]: draft,
    }));
  }, []);

  const setEditDraft = useCallback((commentId: string, draft: NoteDraft) => {
    setEditDraftsByCommentId((current) => ({
      ...current,
      [commentId]: draft,
    }));
  }, []);

  const submitNote = useCallback(
    async (draft: NoteDraft) => {
      setNoteError(null);

      try {
        await createNote(draft);
      } catch (error) {
        setNoteError(toMutationMessage(error));
        throw error;
      }
    },
    [createNote],
  );

  const submitReply = useCallback(
    async (draft: ThreadReplyDraft) => {
      setReplyErrorTargetKey(null);

      try {
        await replyToItem(draft);
        setReplyDraftsByTargetKey((current) => {
          const { [draft.targetKey]: _discarded, ...rest } = current;
          return rest;
        });
        setActiveReplyTarget((current) =>
          current?.targetKey === draft.targetKey ? null : current,
        );
      } catch (error) {
        setReplyErrorTargetKey(draft.targetKey);
        throw error;
      }
    },
    [replyToItem],
  );

  const submitEdit = useCallback(
    async (draft: CommentEditDraft) => {
      setEditErrorCommentId(null);
      setEditErrorMessage(null);

      try {
        await editComment(draft);
        setEditDraftsByCommentId((current) => {
          const { [draft.commentId]: _discarded, ...rest } = current;
          return rest;
        });
        setActiveEditCommentId((current) =>
          current === draft.commentId ? null : current,
        );
      } catch (error) {
        setEditErrorCommentId(draft.commentId);
        setEditErrorMessage(toMutationMessage(error));
        throw error;
      }
    },
    [editComment],
  );

  return {
    activeReplyTarget,
    activeEditCommentId,
    noteError,
    replyErrorTargetKey,
    editErrorCommentId,
    editErrorMessage,
    replyDraftsByTargetKey,
    editDraftsByCommentId,
    startReply,
    cancelReply,
    startEdit,
    cancelEdit,
    setReplyDraft,
    setEditDraft,
    submitNote,
    submitReply,
    submitEdit,
  };
}
