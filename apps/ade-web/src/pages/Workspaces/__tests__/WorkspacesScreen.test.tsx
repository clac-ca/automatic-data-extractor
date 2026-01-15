import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";
import WorkspacesScreen from "..";

const mockUseWorkspacesQuery = vi.fn();
const mockUseSetDefaultWorkspaceMutation = vi.fn();

vi.mock("@/providers/auth/SessionContext", () => ({
  useSession: () => ({
    user: { permissions: ["workspaces.manage_all"] },
  }),
}));

vi.mock("@/hooks/workspaces", () => ({
  useWorkspacesQuery: (...args: unknown[]) => mockUseWorkspacesQuery(...args),
  useSetDefaultWorkspaceMutation: () => mockUseSetDefaultWorkspaceMutation(),
  DEFAULT_WORKSPACE_PAGE_SIZE: 200,
}));

vi.mock("@/navigation/workspacePaths", () => ({
  getDefaultWorkspacePath: (workspaceId: string) => `/workspaces/${workspaceId}/documents`,
}));

vi.mock("@/lib/workspacePreferences", () => ({
  writePreferredWorkspaceId: () => undefined,
}));

describe("WorkspacesScreen", () => {
  beforeEach(() => {
    mockUseWorkspacesQuery.mockReset();
    mockUseSetDefaultWorkspaceMutation.mockReset();
  });

  it("calls the default workspace mutation for a non-default workspace", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined);
    mockUseSetDefaultWorkspaceMutation.mockReturnValue({
      mutateAsync,
      isPending: false,
    });

    const workspaces = [
      {
        id: "alpha",
        name: "Alpha",
        slug: "alpha",
        roles: [],
        permissions: [],
        is_default: false,
      },
      {
        id: "beta",
        name: "Beta",
        slug: "beta",
        roles: [],
        permissions: [],
        is_default: true,
      },
    ];

    mockUseWorkspacesQuery.mockReturnValue({
      data: {
        items: workspaces,
        meta: {
          limit: 2,
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

    const setDefaultButton = screen.getByRole("button", { name: "Set as default" });

    await userEvent.click(setDefaultButton);

    expect(mutateAsync).toHaveBeenCalledWith("alpha");
  });
});
