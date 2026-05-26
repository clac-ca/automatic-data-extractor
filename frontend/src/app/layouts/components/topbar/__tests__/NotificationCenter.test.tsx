import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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

    const badge = await screen.findByText("47");

    expect(badge).toHaveClass("bg-white", "text-red-700", "ring-red-600");
    expect(badge).not.toHaveClass("bg-destructive", "text-destructive-foreground");

    queryClient.clear();
  });
});
