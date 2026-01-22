import { useCallback } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";

import { useFlattenedPages } from "@/api/pagination";
import {
  createDocumentComment,
  listDocumentComments,
  type DocumentComment,
  type DocumentCommentPage,
} from "@/api/documents";
import { stableId } from "../utils";

const COMMENTS_PAGE_SIZE = 50;

type CommentAuthor = NonNullable<DocumentComment["author"]>;

export type CommentDraft = {
  body: string;
  mentions: CommentAuthor[];
};

type CommentItem = DocumentComment & { optimistic?: boolean };

export function useDocumentComments({
  workspaceId,
  documentId,
  currentUser,
  enabled = true,
}: {
  workspaceId: string;
  documentId: string;
  currentUser: CommentAuthor;
  enabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["document-comments", workspaceId, documentId];

  const query = useInfiniteQuery<DocumentCommentPage>({
    queryKey,
    initialPageParam: null,
    queryFn: ({ pageParam, signal }) =>
      listDocumentComments(
        workspaceId,
        documentId,
        {
          limit: COMMENTS_PAGE_SIZE,
          cursor: typeof pageParam === "string" ? pageParam : null,
        },
        signal,
      ),
    getNextPageParam: (lastPage) =>
      lastPage.meta.hasMore ? lastPage.meta.nextCursor ?? undefined : undefined,
    enabled: enabled && Boolean(workspaceId && documentId),
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });

  const mutation = useMutation<DocumentComment, Error, CommentDraft, { previous?: InfiniteData<DocumentCommentPage> }>({
    mutationFn: (draft) =>
      createDocumentComment(workspaceId, documentId, {
        body: draft.body,
        mentions: draft.mentions.map((mention) => mention.id),
      }),
    onMutate: async (draft) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<InfiniteData<DocumentCommentPage>>(queryKey);

      const optimistic: CommentItem = {
        id: stableId(),
        workspaceId,
        documentId,
        body: draft.body,
        author: currentUser,
        mentions: draft.mentions,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        optimistic: true,
      };

      queryClient.setQueryData<InfiniteData<DocumentCommentPage>>(queryKey, (current) => {
        if (!current) {
          return {
            pageParams: [null],
            pages: [
              {
                items: [optimistic],
                meta: {
                  limit: COMMENTS_PAGE_SIZE,
                  hasMore: false,
                  nextCursor: null,
                  totalIncluded: false,
                  totalCount: null,
                  changesCursor: null,
                },
                facets: null,
              },
            ],
          };
        }

        const pages = [...current.pages];
        const lastIndex = Math.max(0, pages.length - 1);
        const last = pages[lastIndex];
        const items = [...(last.items ?? []), optimistic];
        pages[lastIndex] = { ...last, items };
        return { ...current, pages };
      });

      return { previous };
    },
    onError: (_error, _draft, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const pages = query.data?.pages ?? [];
  const comments = useFlattenedPages(pages, (comment) => comment.id) as CommentItem[];

  const submitComment = useCallback(
    (draft: CommentDraft) => mutation.mutateAsync(draft),
    [mutation],
  );

  return {
    ...query,
    comments,
    submitComment,
    isSubmitting: mutation.isPending,
    submitError: mutation.error instanceof Error ? mutation.error.message : null,
  };
}
