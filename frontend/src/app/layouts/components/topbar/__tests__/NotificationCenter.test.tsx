import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationCenter } from "@/app/layouts/components/topbar/NotificationCenter";
import {
  listUserNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
  type UserNotification,
} from "@/api/documents";
import { WorkspaceProvider } from "@/pages/Workspace/context/WorkspaceContext";
import type { WorkspaceProfile } from "@/types/workspaces";

const mockNavigate = vi.hoisted(() => vi.fn());

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/api/documents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/documents")>();
  return {
    ...actual,
    listUserNotifications: vi.fn(),
    markNotificationAsRead: vi.fn(),
    markAllNotificationsAsRead: vi.fn(),
  };
});

const mockListUserNotifications = vi.mocked(listUserNotifications);
const mockMarkNotificationAsRead = vi.mocked(markNotificationAsRead);
const mockMarkAllNotificationsAsRead = vi.mocked(markAllNotificationsAsRead);

const workspace: WorkspaceProfile = {
  id: "workspace-1",
  name: "Workspace",
  slug: "workspace",
  roles: [],
  permissions: [],
  is_default: true,
  processing_paused: false,
};

function renderNotificationCenter() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <WorkspaceProvider workspace={workspace} workspaces={[workspace]}>
          <NotificationCenter />
        </WorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return {
    ...rendered,
    queryClient,
  };
}

function buildNotification(index: number): UserNotification {
  return {
    id: `notification-${index}`,
    workspaceId: workspace.id,
    isRead: false,
    createdAt: "2026-05-26T12:00:00.000Z",
    documentId: `document-${index}`,
    documentName: `Document ${index}`,
    documentDeletedAt: null,
    comment: {
      id: `comment-${index}`,
      workspaceId: workspace.id,
      documentId: `document-${index}`,
      threadId: `thread-${index}`,
      body: "Please review this.",
      author: {
        id: `user-${index}`,
        email: "author@example.com",
        name: "Author",
      },
      mentions: [],
      createdAt: "2026-05-26T12:00:00.000Z",
      updatedAt: "2026-05-26T12:00:00.000Z",
      editedAt: null,
    },
  };
}

describe("NotificationCenter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();
    mockListUserNotifications.mockResolvedValue(Array.from({ length: 47 }, (_, index) => buildNotification(index)));
    mockMarkNotificationAsRead.mockImplementation(async (_workspaceId, notificationId) => buildNotification(Number(notificationId)));
    mockMarkAllNotificationsAsRead.mockResolvedValue();
  });

  afterEach(() => {
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders the unread count badge with high contrast in the red theme", async () => {
    document.documentElement.dataset.theme = "default";
    const { queryClient } = renderNotificationCenter();

    const trigger = screen.getByRole("button", { name: "Open notifications menu" });
    const badge = await screen.findByText("47");

    expect(trigger).toHaveClass("hover:text-accent-foreground");
    expect(badge).toHaveClass("bg-white", "text-red-700", "ring-red-600");
    expect(badge).not.toHaveClass("bg-destructive", "text-destructive-foreground");

    queryClient.clear();
  });

  it("navigates archived notifications to the activity tab with a highlight target", async () => {
    const user = userEvent.setup();
    const notification = {
      ...buildNotification(1),
      documentDeletedAt: "2026-05-27T12:00:00.000Z",
    };
    mockListUserNotifications.mockResolvedValue([notification]);

    const { queryClient } = renderNotificationCenter();

    await user.click(await screen.findByRole("button", { name: "Open notifications menu" }));
    await user.click(await screen.findByText("Document 1"));

    expect(mockNavigate).toHaveBeenCalledWith(
      "/workspaces/workspace-1/documents/document-1?tab=activity&highlightCommentId=comment-1&lifecycle=archived",
    );

    queryClient.clear();
  });

  it("navigates output-file notifications to their source document without comment highlighting", async () => {
    const user = userEvent.setup();
    const notification = {
      ...buildNotification(2),
      documentId: "source-document-2",
      documentDeletedAt: "2026-05-27T12:00:00.000Z",
    };
    mockListUserNotifications.mockResolvedValue([notification]);

    const { queryClient } = renderNotificationCenter();

    await user.click(await screen.findByRole("button", { name: "Open notifications menu" }));
    await user.click(await screen.findByText("Document 2"));

    expect(mockNavigate).toHaveBeenCalledWith(
      "/workspaces/workspace-1/documents/source-document-2?tab=activity&lifecycle=archived",
    );

    queryClient.clear();
  });
});
