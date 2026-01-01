import type { ReactNode } from "react";

import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@test/test-utils";
import WorkspacesScreen from "..";

const mockUseWorkspacesQuery = vi.fn();
const mockUseSetDefaultWorkspaceMutation = vi.fn();

vi.mock("@components/providers/auth/SessionContext", () => ({
  useSession: () => ({
    user: { permissions: ["workspaces.manage_all"] },
  }),
}));

vi.mock("@hooks/workspaces", () => ({
  useWorkspacesQuery: (...args: unknown[]) => mockUseWorkspacesQuery(...args),
  useSetDefaultWorkspaceMutation: () => mockUseSetDefaultWorkspaceMutation(),
}));

vi.mock("@app/navigation/workspacePaths", () => ({
  getDefaultWorkspacePath: (workspaceId: string) => `/workspaces/${workspaceId}/documents`,
}));

vi.mock("@lib/workspacePreferences", () => ({
  writePreferredWorkspaceId: () => undefined,
}));

vi.mock("@pages/Workspaces/components/WorkspaceDirectoryLayout", () => ({
  WorkspaceDirectoryLayout: ({ children }: { readonly children: ReactNode }) => (
    <div data-testid="workspace-layout">{children}</div>
  ),
}));

vi.mock("@components/shell/GlobalSearchField", () => ({
  GlobalSearchField: (props: { className?: string }) => (
    <div data-testid="global-search" className={props.className} />
  ),
}));

vi.mock("@hooks/useShortcutHint", () => ({
  useShortcutHint: () => undefined,
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

    render(<WorkspacesScreen />);

    const setDefaultButton = screen.getByRole("button", { name: "Set as default" });

    await userEvent.click(setDefaultButton);

    expect(mutateAsync).toHaveBeenCalledWith("alpha");
  });
});
