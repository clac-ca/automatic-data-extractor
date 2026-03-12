import { useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDocumentActivityComment,
  createDocumentActivityThread,
  deleteDocumentComment,
  getDocumentActivity,
  updateDocumentComment,
} from "@/api/documents";
import { useSession } from "@/providers/auth/SessionContext";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import type {
  ActivityCurrentUser,
  CommentEditDraft,
  ThreadReplyDraft,
  NoteDraft,
} from "../activityTypes";
import {
  buildActivityItems,
  normalizeActivityResponse,
  type ActivityResponseData,
} from "../model";
import { codePointIndexFromCodeUnitIndex } from "../../comments/utils/mentions";
import {
  appendCommentToThread,
  appendOptimisticNote,
  attachThreadToActivityItem,
  buildOptimisticComment,
  buildOptimisticThread,
  ensureActivityData,
  removeCommentFromActivity,
  updateCommentInActivity,
} from "./activityTimelineCache";

type CreateThreadMutationInput = {
  targetKey: string;
  anchorType: "note" | "document" | "run";
  anchorId?: string | null;
  body: string;
  mentions: NoteDraft["mentions"];
};

type CreateCommentMutationInput = ThreadReplyDraft & {
  threadId: string;
};

function serializeMentions(body: string, mentions: NoteDraft["mentions"]) {
  return mentions.map((mention) => ({
    userId: mention.user.id,
    start: codePointIndexFromCodeUnitIndex(body, mention.start),
    end: codePointIndexFromCodeUnitIndex(body, mention.end),
  }));
}

function decrementCommentCount(document: DocumentRow | undefined): DocumentRow | undefined {
  if (!document) {
    return document;
  }

  return {
    ...document,
    commentCount: Math.max(0, (document.commentCount ?? 0) - 1),
  };
}

function toMutationMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unable to delete that comment right now.";
}

export function useDocumentActivityTimeline({
  workspaceId,
  document,
}: {
  workspaceId: string;
  document: DocumentRow;
}) {
  const session = useSession();
  const queryClient = useQueryClient();
  const queryKey = ["document-activity", workspaceId, document.id] as const;
  const detailQueryKey = ["documents-detail", workspaceId, document.id] as const;
  const documentsListQueryKey = ["documents", workspaceId] as const;

  const currentUser = useMemo<ActivityCurrentUser>(
    () => ({
      id: session.user.id,
      name: session.user.display_name || session.user.email || null,
      email: session.user.email ?? "",
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );

  const activityQuery = useQuery<ActivityResponseData>({
    queryKey,
    queryFn: async ({ signal }) =>
      normalizeActivityResponse(await getDocumentActivity(workspaceId, document.id, signal)),
    enabled: Boolean(workspaceId && document.id),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });

  const createThreadMutation = useMutation<
    unknown,
    Error,
    CreateThreadMutationInput,
    { previous?: ActivityResponseData }
  >({
    mutationFn: async (draft) =>
      createDocumentActivityThread(workspaceId, document.id, {
        anchorType: draft.anchorType,
        anchorId: draft.anchorId ?? null,
        body: draft.body,
        mentions: serializeMentions(draft.body, draft.mentions),
      }),
    onMutate: async (draft) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<ActivityResponseData>(queryKey);
      const now = new Date().toISOString();

      if (draft.anchorType === "note") {
        const thread = buildOptimisticThread({
          workspaceId,
          documentId: document.id,
          anchorType: "note",
          currentUser,
          body: draft.body,
          mentions: draft.mentions,
          activityAt: now,
          pendingAction: "create",
        });

        queryClient.setQueryData<ActivityResponseData>(queryKey, (current) =>
          appendOptimisticNote(current, {
            key: `note:${thread.id}`,
            replyTargetKey: `note:${thread.id}`,
            id: thread.id,
            type: "note",
            activityAt: now,
            thread,
          }),
        );
      } else if (draft.anchorId) {
        const anchorType = draft.anchorType as "document" | "run";
        const current = ensureActivityData(previous);
        const anchorItem = current.items.find(
          (item) => item.type === anchorType && item.id === draft.anchorId,
        );

        queryClient.setQueryData<ActivityResponseData>(queryKey, (value) =>
          attachThreadToActivityItem(
            value,
            anchorType,
            draft.anchorId!,
            buildOptimisticThread({
              workspaceId,
              documentId: document.id,
              anchorType,
              anchorId: draft.anchorId,
              currentUser,
              body: draft.body,
              mentions: draft.mentions,
              activityAt: anchorItem?.activityAt ?? now,
              pendingAction: "reply",
            }),
          ),
        );
      }

      return { previous };
    },
    onError: (_error, _draft, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  const createCommentMutation = useMutation<
    unknown,
    Error,
    CreateCommentMutationInput,
    { previous?: ActivityResponseData }
  >({
    mutationFn: async (draft) =>
      createDocumentActivityComment(workspaceId, document.id, draft.threadId, {
        body: draft.body,
        mentions: serializeMentions(draft.body, draft.mentions),
      }),
    onMutate: async (draft) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<ActivityResponseData>(queryKey);

      queryClient.setQueryData<ActivityResponseData>(queryKey, (current) =>
        appendCommentToThread(
          current,
          draft.threadId,
          buildOptimisticComment({
            workspaceId,
            documentId: document.id,
            threadId: draft.threadId,
            currentUser,
            body: draft.body,
            mentions: draft.mentions,
            pendingAction: "reply",
          }),
        ),
      );

      return { previous };
    },
    onError: (_error, _draft, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  const updateCommentMutation = useMutation<
    unknown,
    Error,
    CommentEditDraft,
    { previous?: ActivityResponseData }
  >({
    mutationFn: async (draft) =>
      updateDocumentComment(workspaceId, document.id, draft.commentId, {
        body: draft.body,
        mentions: serializeMentions(draft.body, draft.mentions),
      }),
    onMutate: async (draft) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<ActivityResponseData>(queryKey);
      const now = new Date().toISOString();

      queryClient.setQueryData<ActivityResponseData>(queryKey, (current) =>
        updateCommentInActivity(current, draft.commentId, (comment) => ({
          ...comment,
          body: draft.body,
          mentions: draft.mentions.map((mention) => ({
            user: mention.user,
            start: mention.start,
            end: mention.end,
          })),
          updatedAt: now,
          editedAt: now,
          optimistic: true,
          pendingAction: "edit",
        })),
      );

      return { previous };
    },
    onError: (_error, _draft, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  const deleteCommentMutation = useMutation<
    void,
    Error,
    { commentId: string },
    {
      previousActivity?: ActivityResponseData;
      previousDetail?: DocumentRow;
    }
  >({
    mutationFn: async ({ commentId }) => deleteDocumentComment(workspaceId, document.id, commentId),
    onMutate: async ({ commentId }) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey }),
        queryClient.cancelQueries({ queryKey: detailQueryKey }),
      ]);

      const previousActivity = queryClient.getQueryData<ActivityResponseData>(queryKey);
      const previousDetail = queryClient.getQueryData<DocumentRow>(detailQueryKey);

      queryClient.setQueryData<ActivityResponseData>(queryKey, (current) =>
        removeCommentFromActivity(current, commentId),
      );
      queryClient.setQueryData<DocumentRow | undefined>(detailQueryKey, (current) =>
        decrementCommentCount(current),
      );

      return { previousActivity, previousDetail };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousActivity) {
        queryClient.setQueryData(queryKey, context.previousActivity);
      }
      if (context?.previousDetail) {
        queryClient.setQueryData(detailQueryKey, context.previousDetail);
      }
    },
    onSettled: () => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey }),
        queryClient.invalidateQueries({ queryKey: detailQueryKey }),
        queryClient.invalidateQueries({ queryKey: documentsListQueryKey }),
      ]);
    },
  });

  const createNote = useCallback(
    async (draft: NoteDraft) => {
      await createThreadMutation.mutateAsync({
        targetKey: "note-composer",
        anchorType: "note",
        body: draft.body,
        mentions: draft.mentions,
      });
    },
    [createThreadMutation],
  );

  const replyToItem = useCallback(
    async (draft: ThreadReplyDraft) => {
      if (draft.threadId) {
        await createCommentMutation.mutateAsync({
          ...draft,
          threadId: draft.threadId,
        });
        return;
      }

      if (!draft.anchorType || !draft.anchorId) {
        throw new Error("Reply target is missing thread or anchor details.");
      }

      await createThreadMutation.mutateAsync({
        targetKey: draft.targetKey,
        anchorType: draft.anchorType,
        anchorId: draft.anchorId,
        body: draft.body,
        mentions: draft.mentions,
      });
    },
    [createCommentMutation, createThreadMutation],
  );

  const editComment = useCallback(
    async (draft: CommentEditDraft) => {
      await updateCommentMutation.mutateAsync(draft);
    },
    [updateCommentMutation],
  );

  const removeComment = useCallback(
    async (commentId: string) => {
      await deleteCommentMutation.mutateAsync({ commentId });
    },
    [deleteCommentMutation],
  );

  const items = useMemo(
    () => buildActivityItems(activityQuery.data ?? { items: [] }),
    [activityQuery.data],
  );

  const replyingTargetKey =
    createCommentMutation.isPending
      ? createCommentMutation.variables?.targetKey ?? null
      : createThreadMutation.isPending && createThreadMutation.variables?.anchorType !== "note"
        ? createThreadMutation.variables?.targetKey ?? null
        : null;

  const editingCommentId =
    updateCommentMutation.isPending ? updateCommentMutation.variables?.commentId ?? null : null;
  const deletingCommentId =
    deleteCommentMutation.isPending ? deleteCommentMutation.variables?.commentId ?? null : null;
  const deleteErrorCommentId =
    deleteCommentMutation.isError ? deleteCommentMutation.variables?.commentId ?? null : null;
  const deleteErrorMessage = deleteCommentMutation.isError
    ? toMutationMessage(deleteCommentMutation.error)
    : null;

  return {
    currentUser,
    items,
    isLoading: activityQuery.isLoading,
    hasError: Boolean(activityQuery.error),
    createNote,
    replyToItem,
    editComment,
    removeComment,
    isCreatingNote:
      createThreadMutation.isPending && createThreadMutation.variables?.anchorType === "note",
    replyingTargetKey,
    editingCommentId,
    deletingCommentId,
    deleteErrorCommentId,
    deleteErrorMessage,
  };
}
