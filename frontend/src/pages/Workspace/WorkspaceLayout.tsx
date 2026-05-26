import { useEffect, useRef, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { WorkspaceSidebar } from "@/pages/Workspace/components/WorkspaceSidebar";
import { WorkspaceTopbar } from "@/pages/Workspace/components/WorkspaceTopbar";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useNotifications } from "@/providers/notifications/useNotifications";
import { listUserNotifications, type UserNotification } from "@/api/documents";

export function WorkspaceLayout({ children }: { readonly children: ReactNode }) {
  const { workspace } = useWorkspaceContext();
  const { notifyToast } = useNotifications();

  const queryKey = ["notifications", workspace.id];
  const { data: notifications } = useQuery({
    queryKey,
    queryFn: () => listUserNotifications(workspace.id),
    enabled: Boolean(workspace.id),
    staleTime: 5000,
  });

  const prevNotificationsRef = useRef<UserNotification[] | null>(null);

  useEffect(() => {
    if (!notifications) return;
    if (prevNotificationsRef.current === null) {
      prevNotificationsRef.current = notifications;
      return;
    }

    const prevUnreadIds = new Set(
      prevNotificationsRef.current.filter((n) => !n.isRead).map((n) => n.id)
    );

    const newMentions = notifications.filter(
      (n) => !n.isRead && !prevUnreadIds.has(n.id)
    );

    prevNotificationsRef.current = notifications;

    newMentions.forEach((mention) => {
      const authorName = mention.comment.author?.name || mention.comment.author?.email || "Someone";
      notifyToast({
        title: "New Mention!",
        description: `${authorName} mentioned you in ${mention.documentName}: "${mention.comment.body}"`,
        intent: "success",
        duration: 6000,
      });
    });
  }, [notifications, notifyToast]);

  return (
    <SidebarProvider defaultOpen={false} className="flex h-svh w-full overflow-hidden">
      <WorkspaceSidebar />

      <SidebarInset className="min-h-0 min-w-0 overflow-hidden">
        <WorkspaceTopbar />

        <div
          data-slot="workspace-content"
          className="relative min-h-0 min-w-0 flex-1 overflow-auto"
        >
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
