import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceRunsForDocument } from "@/api/runs/api";
import { useSession } from "@/providers/auth/SessionContext";
import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import {
  useDocumentComments,
  type CommentDraft,
} from "../../comments/hooks/useDocumentComments";
import {
  buildActivityItems,
  filterActivityItems,
  getActivityCounts,
} from "../model";

export type ActivityCurrentUser = {
  id: string;
  name: string | null;
  email: string;
};

export type ActivityFeedModel = {
  currentUser: ActivityCurrentUser;
  visibleItems: ReturnType<typeof filterActivityItems>;
  counts: ReturnType<typeof getActivityCounts>;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  isLoading: boolean;
  hasError: boolean;
  submitError: string | null;
  isSubmitting: boolean;
  submitComment: (draft: CommentDraft) => void;
  fetchNextPage: () => void;
};

export function useDocumentActivityFeed({
  workspaceId,
  document,
  filter,
}: {
  workspaceId: string;
  document: DocumentRow;
  filter: DocumentActivityFilter;
}): ActivityFeedModel {
  const session = useSession();

  const currentUser = useMemo<ActivityCurrentUser>(
    () => ({
      id: session.user.id,
      name: session.user.display_name || session.user.email || null,
      email: session.user.email ?? "",
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );

  const commentsModel = useDocumentComments({
    workspaceId,
    documentId: document.id,
    currentUser,
  });

  const runsQuery = useQuery({
    queryKey: ["document-activity-runs", workspaceId, document.id],
    queryFn: ({ signal }) =>
      fetchWorkspaceRunsForDocument(workspaceId, document.id, signal),
    enabled: Boolean(workspaceId && document.id),
    staleTime: 30_000,
  });

  const allItems = useMemo(
    () => buildActivityItems(document, runsQuery.data ?? [], commentsModel.comments),
    [commentsModel.comments, document, runsQuery.data],
  );

  const visibleItems = useMemo(
    () => filterActivityItems(allItems, filter),
    [allItems, filter],
  );

  const counts = useMemo(() => getActivityCounts(allItems), [allItems]);

  return {
    currentUser,
    visibleItems,
    counts,
    hasNextPage: Boolean(commentsModel.hasNextPage),
    isFetchingNextPage: commentsModel.isFetchingNextPage,
    isLoading: runsQuery.isLoading || commentsModel.isLoading,
    hasError: Boolean(runsQuery.error || commentsModel.error),
    submitError: commentsModel.submitError,
    isSubmitting: commentsModel.isSubmitting,
    submitComment(draft: CommentDraft) {
      void commentsModel.submitComment(draft);
    },
    fetchNextPage() {
      void commentsModel.fetchNextPage();
    },
  };
}
