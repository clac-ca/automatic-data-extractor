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
  const debouncedQuery = useDebouncedValue(query?.trim() ?? "", 180);

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
    placeholderData: (previous) => previous,
  });

  const mentionSuggestions = useMemo<CommentComposerUser[]>(() => {
    const members = membersQuery.data?.items ?? [];
    return members.map((member) => ({
      id: member.user_id,
      name: member.user?.display_name ?? null,
      email: member.user?.email ?? `${member.user_id}@workspace.local`,
    }));
  }, [membersQuery.data?.items]);

  return {
    mentionSuggestions,
    isMentionLoading: membersQuery.isFetching,
    hasMentionResults: mentionSuggestions.length > 0,
  };
}
