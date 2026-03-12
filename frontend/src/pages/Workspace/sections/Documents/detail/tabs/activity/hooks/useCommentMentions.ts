import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listWorkspaceMembers } from "@/api/workspaces/api";
import type { CommentComposerUser } from "@/pages/Workspace/sections/Documents/detail/tabs/comments/components/CommentComposer";

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timeoutId);
  }, [delayMs, value]);

  return debounced;
}

export function useCommentMentions(workspaceId: string, query: string | null) {
  const normalizedQuery = query?.trim() ?? "";
  const debouncedQuery = useDebouncedValue(normalizedQuery, 180);
  const hasFreshResults = query !== null && normalizedQuery === debouncedQuery;

  const membersQuery = useQuery({
    queryKey: ["comment-mentions", workspaceId, debouncedQuery],
    queryFn: ({ signal }) =>
      listWorkspaceMembers(workspaceId, {
        limit: 8,
        q: debouncedQuery || undefined,
        signal,
      }),
    enabled: Boolean(workspaceId && query !== null),
    staleTime: 30_000,
  });

  const mentionSuggestions = useMemo<CommentComposerUser[]>(() => {
    if (!hasFreshResults) {
      return [];
    }

    const members = membersQuery.data?.items ?? [];
    return members.map((member) => ({
      id: member.user_id,
      name: member.user?.display_name ?? null,
      email: member.user?.email ?? `${member.user_id}@workspace.local`,
    }));
  }, [hasFreshResults, membersQuery.data?.items]);

  return {
    mentionSuggestions,
    isMentionLoading: query !== null && (!hasFreshResults || membersQuery.isFetching),
    hasMentionResults: mentionSuggestions.length > 0,
  };
}
