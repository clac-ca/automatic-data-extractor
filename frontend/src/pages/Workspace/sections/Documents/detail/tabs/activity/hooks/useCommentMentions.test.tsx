import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listWorkspaceMembers } from "@/api/workspaces/api";

import { useCommentMentions } from "./useCommentMentions";

vi.mock("@/api/workspaces/api", () => ({
  listWorkspaceMembers: vi.fn(),
}));

const listWorkspaceMembersMock = vi.mocked(listWorkspaceMembers);

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useCommentMentions", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("hides stale suggestions until the debounced query catches up", async () => {
    listWorkspaceMembersMock.mockImplementation(async (_workspaceId, options = {}) => ({
      items: options.q === "ad"
        ? [
            {
              user_id: "user-1",
              role_ids: [],
              role_slugs: [],
              created_at: "2026-01-01T00:00:00Z",
              user: {
                id: "user-1",
                email: "ada@example.com",
                display_name: "Ada Lovelace",
              },
            },
          ]
        : [],
      meta: {
        nextCursor: null,
        limit: 8,
        hasMore: false,
        totalIncluded: true,
        totalCount: options.q === "ad" ? 1 : 0,
      },
      facets: {},
    }));

    const { result, rerender } = renderHook(
      ({ query }) => useCommentMentions("ws-1", query),
      {
        initialProps: { query: "ad" as string | null },
        wrapper: createWrapper(),
      },
    );

    await waitFor(() => {
      expect(result.current.mentionSuggestions).toHaveLength(1);
    });

    rerender({ query: "zz" });

    expect(result.current.mentionSuggestions).toEqual([]);
    expect(result.current.isMentionLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.mentionSuggestions).toEqual([]);
      expect(result.current.isMentionLoading).toBe(false);
    });
  });
});
