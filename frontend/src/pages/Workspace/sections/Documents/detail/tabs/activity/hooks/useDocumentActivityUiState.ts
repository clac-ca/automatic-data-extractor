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

  const startReply = useCallback((target: ActivityReplyTarget) => {
    setActiveEditCommentId(null);
    setEditErrorCommentId(null);
    setEditErrorMessage(null);
    setReplyErrorTargetKey(null);
    setActiveReplyTarget(target);
  }, []);

  const cancelReply = useCallback(() => {
    setReplyErrorTargetKey(null);
    setActiveReplyTarget(null);
  }, []);

  const startEdit = useCallback((commentId: string) => {
    setActiveReplyTarget(null);
    setReplyErrorTargetKey(null);
    setEditErrorCommentId(null);
    setEditErrorMessage(null);
    setActiveEditCommentId(commentId);
  }, []);

  const cancelEdit = useCallback(() => {
    setEditErrorCommentId(null);
    setEditErrorMessage(null);
    setActiveEditCommentId(null);
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
    startReply,
    cancelReply,
    startEdit,
    cancelEdit,
    submitNote,
    submitReply,
    submitEdit,
  };
}
