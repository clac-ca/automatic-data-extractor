import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

import DocumentsListPage from "../DocumentsListPage";

vi.mock("@/providers/auth/SessionContext", () => ({
  useSession: () => ({
    user: {
      id: "user-1",
      email: "user@example.com",
      display_name: "User Example",
    },
  }),
}));

vi.mock("@/providers/notifications", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/providers/notifications")>();
  return {
    ...actual,
    useNotifications: () => ({
      notifyToast: vi.fn(),
    }),
  };
});

vi.mock("@/pages/Workspace/context/WorkspaceContext", () => ({
  useWorkspaceContext: () => ({
    workspace: {
      id: "ws-1",
      processing_paused: false,
    },
  }),
}));

vi.mock("@/pages/Workspace/hooks/configurations", () => ({
  useConfigurationsQuery: () => ({
    data: {
      items: [{ id: "cfg-1", status: "active" }],
    },
    isSuccess: true,
  }),
}));

vi.mock("@/pages/Workspace/sections/Documents/list/upload/useUploadManager", () => ({
  useUploadManager: () => ({
    items: [],
    summary: {
      active: 0,
      queued: 0,
      completed: 0,
      failed: 0,
      conflicts: 0,
      total: 0,
    },
    enqueue: () => [],
    pause: vi.fn(),
    resume: vi.fn(),
    retry: vi.fn(),
    resolveConflict: vi.fn(),
    resolveAllConflicts: vi.fn(),
    cancel: vi.fn(),
    remove: vi.fn(),
    clearCompleted: vi.fn(),
  }),
}));

vi.mock("@/pages/Workspace/sections/Documents/list/upload/UploadManager", () => ({
  UploadManager: () => <div data-testid="upload-manager" />,
}));

vi.mock("@/pages/Workspace/sections/Documents/list/upload/UploadPreflightDialog", () => ({
  UploadPreflightDialog: () => null,
}));

vi.mock("@/pages/Workspace/sections/Documents/list/table/DocumentsTableView", () => ({
  DocumentsTableView: () => <div data-testid="documents-table-view" />,
}));

describe("DocumentsListPage layout", () => {
  it("uses top-only section padding so the table footer can sit at the bottom edge", () => {
    render(<DocumentsListPage />, { route: "/workspaces/ws-1/documents" });

    const section = screen.getByTestId("documents-table-view").parentElement;
    expect(section).not.toBeNull();
    expect(section).toHaveClass("pt-3");
    expect(section).not.toHaveClass("py-3");
  });
});
