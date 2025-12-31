import type { ReactNode } from "react";

import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@test/test-utils";
import WorkspacesIndexRoute from "..";

const mockUseWorkspacesQuery = vi.fn();
const mockUseSetDefaultWorkspaceMutation = vi.fn();

vi.mock("@components/auth/RequireSession", () => ({
  RequireSession: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@components/auth/SessionContext", () => ({
  useSession: () => ({
    user: { permissions: ["workspaces.manage_all"] },
  }),
}));

vi.mock("@hooks/workspaces", () => ({
  useWorkspacesQuery: (...args: unknown[]) => mockUseWorkspacesQuery(...args),
  useSetDefaultWorkspaceMutation: () => mockUseSetDefaultWorkspaceMutation(),
}));

vi.mock("@utils/workspaces", () => ({
  getDefaultWorkspacePath: (workspaceId: string) => `/workspaces/${workspaceId}/documents`,
  writePreferredWorkspaceId: () => undefined,
}));

vi.mock("@pages/Workspaces/components/WorkspaceDirectoryLayout", () => ({
  WorkspaceDirectoryLayout: ({ children }: { readonly children: ReactNode }) => (
    <div data-testid="workspace-layout">{children}</div>
  ),
}));

vi.mock("@app/shell/GlobalSearchField", () => ({
  GlobalSearchField: (props: { className?: string }) => (
    <div data-testid="global-search" className={props.className} />
  ),
}));

vi.mock("@hooks/useShortcutHint", () => ({
  useShortcutHint: () => undefined,
}));

describe("WorkspacesIndexRoute", () => {
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
        page: 1,
        page_size: 2,
        has_next: false,
        has_previous: false,
        total: 2,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<WorkspacesIndexRoute />);

    const setDefaultButton = screen.getByRole("button", { name: "Set as default" });

    await userEvent.click(setDefaultButton);

    expect(mutateAsync).toHaveBeenCalledWith("alpha");
  });
});
