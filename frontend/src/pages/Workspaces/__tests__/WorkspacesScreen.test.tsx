import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";
import WorkspacesScreen from "..";

const mockUseWorkspacesQuery = vi.fn();

vi.mock("@/providers/auth/SessionContext", () => ({
  useSession: () => ({
    user: { permissions: ["workspaces.manage_all"] },
  }),
}));

vi.mock("@/hooks/workspaces", () => ({
  useWorkspacesQuery: (...args: unknown[]) => mockUseWorkspacesQuery(...args),
}));

describe("WorkspacesScreen", () => {
  beforeEach(() => {
    mockUseWorkspacesQuery.mockReset();
  });

  it("renders a minimal workspace selector with simple rows", () => {
    mockUseWorkspacesQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "alpha",
            name: "Alpha",
            slug: "alpha",
            roles: [],
            permissions: ["workspace.documents.read"],
            is_default: false,
            processing_paused: false,
          },
          {
            id: "beta",
            name: "Beta",
            slug: "beta",
            roles: [],
            permissions: ["workspace.documents.manage"],
            is_default: true,
            processing_paused: true,
          },
        ],
        meta: {
          limit: 25,
          hasMore: false,
          nextCursor: null,
          totalIncluded: true,
          totalCount: 2,
          changesCursor: "0",
        },
        facets: null,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<WorkspacesScreen />);

    expect(screen.queryByRole("searchbox", { name: "Search workspaces" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open workspace Alpha" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open workspace Beta" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sort" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Filter" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set as default" })).not.toBeInTheDocument();
    expect(screen.queryByText("Permissions")).not.toBeInTheDocument();
    expect(screen.queryByText("Processing active")).not.toBeInTheDocument();
    expect(screen.queryByText("Processing paused")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "New workspace" })).toHaveLength(1);
  });

  it("shows a no-results message for a search query", () => {
    mockUseWorkspacesQuery.mockReturnValue({
      data: {
        items: [],
        meta: {
          limit: 25,
          hasMore: false,
          nextCursor: null,
          totalIncluded: true,
          totalCount: 0,
          changesCursor: "0",
        },
        facets: null,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<WorkspacesScreen />, { route: "/workspaces?q=nomatch" });

    expect(screen.getByText("No workspaces found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear search" })).toBeInTheDocument();
  });
});
