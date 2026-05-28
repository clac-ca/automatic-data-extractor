import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Bell, Check, CheckCheck, Clock, Sparkles } from "lucide-react";

import {
  listUserNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead,
  type UserNotification,
} from "@/api/documents";
import { useOptionalWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import type { WorkspaceProfile } from "@/types/workspaces";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { buildDocumentDetailUrl } from "@/pages/Workspace/sections/Documents/shared/navigation";
import { cn } from "@/lib/utils";

function timeAgo(dateString: string | Date): string {
  const date = typeof dateString === "string" ? new Date(dateString) : dateString;
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 5) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

function getInitials(name?: string | null, email?: string): string {
  if (name && name.trim()) {
    return name
      .split(" ")
      .filter(Boolean)
      .map((n) => n[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
  }
  return email ? email[0].toUpperCase() : "?";
}

export function NotificationCenter() {
  const context = useOptionalWorkspaceContext();
  const workspace = context?.workspace;

  if (!workspace) {
    return null;
  }

  return <NotificationCenterInner workspace={workspace} />;
}

function NotificationCenterInner({ workspace }: { readonly workspace: WorkspaceProfile }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const queryKey = useMemo(() => ["notifications", workspace.id], [workspace.id]);

  const notificationsQuery = useQuery({
    queryKey,
    queryFn: () => listUserNotifications(workspace.id),
    enabled: Boolean(workspace.id),
    refetchInterval: 15_000, // Background poll every 15s to capture mentions out-of-document
  });

  const notifications = notificationsQuery.data ?? [];
  const unreadNotifications = useMemo(() => notifications.filter((n) => !n.isRead), [notifications]);
  const unreadCount = unreadNotifications.length;

  const markReadMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationAsRead(workspace.id, notificationId),
    onSuccess: (updated) => {
      queryClient.setQueryData<UserNotification[]>(queryKey, (current) => {
        if (!current) return current;
        return current.map((n) => (n.id === updated.id ? updated : n));
      });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => markAllNotificationsAsRead(workspace.id),
    onSuccess: () => {
      queryClient.setQueryData<UserNotification[]>(queryKey, (current) => {
        if (!current) return current;
        return current.map((n) => ({ ...n, isRead: true }));
      });
    },
  });

  const handleNotificationClick = async (notif: UserNotification) => {
    setOpen(false);
    if (!notif.isRead) {
      markReadMutation.mutate(notif.id);
    }
    // Navigate directly to the document details page activity tab and pass the comment ID to glow focus it
    const url = buildDocumentDetailUrl(workspace.id, notif.documentId, {
      tab: "activity",
      highlightCommentId: notif.comment.documentId === notif.documentId ? notif.comment.id : null,
      lifecycle: notif.documentDeletedAt ? "archived" : "active",
    });
    navigate(url);
  };

  const handleMarkAsRead = (e: React.MouseEvent, notifId: string) => {
    e.stopPropagation();
    markReadMutation.mutate(notifId);
  };

  const handleMarkAllAsRead = (e: React.MouseEvent) => {
    e.stopPropagation();
    markAllReadMutation.mutate();
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "relative inline-flex h-9 w-9 items-center justify-center rounded-full border text-foreground shadow-sm transition",
            "border-border/60 bg-background/80 hover:border-border/90 hover:bg-accent hover:text-accent-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "border-ring bg-accent text-accent-foreground ring-2 ring-ring/30",
          )}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Open notifications menu"
        >
          <Bell
            className={cn(
              "h-[18px] w-[18px] transition-transform duration-300",
              unreadCount > 0 && "text-foreground",
            )}
          />
          {unreadCount > 0 ? (
            <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-white px-1 text-[9px] font-bold text-red-700 shadow-sm ring-2 ring-red-600">
              {unreadCount}
            </span>
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-80 sm:w-96 rounded-xl border-border/70 bg-popover/95 p-0 shadow-lg backdrop-blur-sm overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3 bg-muted/30">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">Notifications</span>
            {unreadCount > 0 ? (
              <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                {unreadCount} unread
              </span>
            ) : null}
          </div>
          {unreadCount > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleMarkAllAsRead}
              className="h-7 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground hover:bg-transparent"
              disabled={markAllReadMutation.isPending}
            >
              <CheckCheck className="h-3.5 w-3.5" />
              <span>Mark all read</span>
            </Button>
          ) : null}
        </div>

        {/* Notifications List */}
        <div className="max-h-[360px] overflow-y-auto divide-y divide-border/50 custom-scrollbar">
          {notificationsQuery.isPending ? (
            <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span className="mt-2 text-xs">Loading notifications...</span>
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-6 text-center select-none">
              <div className="relative flex h-12 w-12 items-center justify-center rounded-full bg-accent/60 text-muted-foreground animate-pulse">
                <Bell className="h-6 w-6" />
                <Sparkles className="absolute -top-1 -right-1 h-4 w-4 text-amber-500" />
              </div>
              <p className="mt-3 text-sm font-medium text-foreground">All caught up!</p>
              <p className="mt-1 text-xs text-muted-foreground leading-normal max-w-[200px]">
                You don't have any comment mentions or workspace alerts right now.
              </p>
            </div>
          ) : (
            notifications.map((notif) => {
              const authorName = notif.comment.author?.name || notif.comment.author?.email || "Someone";
              const authorEmail = notif.comment.author?.email || "";
              const initials = getInitials(notif.comment.author?.name, authorEmail);
              const isUnread = !notif.isRead;

              return (
                <div
                  key={notif.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleNotificationClick(notif)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleNotificationClick(notif);
                    }
                  }}
                  className={cn(
                    "group relative flex w-full items-start gap-3 p-3.5 text-left transition cursor-pointer outline-none focus-visible:bg-accent/30",
                    isUnread
                      ? "bg-primary/5 hover:bg-primary/8 border-l-2 border-l-primary"
                      : "hover:bg-accent/40 border-l-2 border-l-transparent",
                  )}
                >
                  <Avatar className="mt-0.5 h-8 w-8 shrink-0 border border-border/60 shadow-sm">
                    <AvatarFallback className="bg-primary text-[10px] font-bold uppercase text-primary-foreground">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                        Mention
                      </span>
                      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-medium">
                        <Clock className="h-3 w-3" />
                        <span>{timeAgo(notif.createdAt)}</span>
                      </div>
                    </div>
                    <p className="text-xs leading-normal text-foreground">
                      <span className="font-semibold text-foreground">{authorName}</span> mentioned you in a comment on{" "}
                      <span className="font-semibold text-primary hover:underline">{notif.documentName}</span>
                    </p>
                    <blockquote className="rounded bg-muted/65 border-l border-border/80 px-2 py-1 text-[11px] text-muted-foreground truncate leading-relaxed">
                      "{notif.comment.body}"
                    </blockquote>
                  </div>

                  {/* Mark as Read Button */}
                  {isUnread ? (
                    <button
                      type="button"
                      onClick={(e) => handleMarkAsRead(e, notif.id)}
                      className={cn(
                        "opacity-100 sm:opacity-0 group-hover:opacity-100 flex h-5 w-5 items-center justify-center rounded-full bg-background border border-border shadow-sm text-muted-foreground hover:text-primary hover:border-primary/45 transition",
                      )}
                      title="Mark as read"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
