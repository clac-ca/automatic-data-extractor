import { client } from "@/api/client";
import type { components } from "@/types";

export type UserNotification = components["schemas"]["UserNotificationOut"];

export async function listUserNotifications(
  workspaceId: string,
  limit = 50,
): Promise<UserNotification[]> {
  const { data } = await client.GET(
    "/api/v1/workspaces/{workspaceId}/documents/notifications",
    {
      params: { path: { workspaceId }, query: { limit } },
    },
  );
  return data ?? [];
}

export async function markNotificationAsRead(
  workspaceId: string,
  notificationId: string,
): Promise<UserNotification> {
  const { data } = await client.PATCH(
    "/api/v1/workspaces/{workspaceId}/documents/notifications/{notificationId}/read",
    {
      params: { path: { workspaceId, notificationId } },
    },
  );
  if (!data) {
    throw new Error("Expected user notification payload.");
  }
  return data;
}

export async function markAllNotificationsAsRead(
  workspaceId: string,
): Promise<void> {
  await client.POST(
    "/api/v1/workspaces/{workspaceId}/documents/notifications/readAll",
    {
      params: { path: { workspaceId } },
    },
  );
}
