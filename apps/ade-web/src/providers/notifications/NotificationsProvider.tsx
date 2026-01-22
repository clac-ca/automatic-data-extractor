import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { createPortal } from "react-dom";

import type { BannerOptions, NotificationAction, NotificationIntent, ToastOptions } from "./types";
import { CloseIcon, ErrorIcon, InfoIcon, SuccessIcon, WarningIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Stack, StackItem } from "@/components/ui/stack";
import { cn } from "@/lib/utils";

interface ToastEntry {
  readonly kind: "toast";
  readonly id: string;
  readonly title: string;
  readonly description?: string;
  readonly intent: NotificationIntent;
  readonly actions: readonly NotificationAction[];
  readonly duration: number | null;
  readonly dismissible: boolean;
  readonly scope?: string;
  readonly persistKey?: string;
  readonly icon?: BannerOptions["icon"];
  readonly createdAt: number;
}

interface BannerEntry {
  readonly kind: "banner";
  readonly id: string;
  readonly title: string;
  readonly description?: string;
  readonly intent: NotificationIntent;
  readonly actions: readonly NotificationAction[];
  readonly duration: number | null;
  readonly dismissible: boolean;
  readonly scope?: string;
  readonly persistKey?: string;
  readonly icon?: BannerOptions["icon"];
  readonly sticky: boolean;
  readonly createdAt: number;
}

interface NotificationsContextValue {
  readonly toasts: readonly ToastEntry[];
  readonly banners: readonly BannerEntry[];
  readonly pushToast: (options: ToastOptions) => string;
  readonly pushBanner: (options: BannerOptions) => string;
  readonly dismiss: (id: string) => void;
  readonly clearScope: (scope: string, kind?: "toast" | "banner") => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

const DEFAULT_TOAST_DURATION = 6000;
const DEFAULT_BANNER_DURATION = 7000;
const TOAST_STACK_COLLAPSED_COUNT = 3;
const BANNER_STACK_COLLAPSED_COUNT = 2;

export function NotificationsProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const [banners, setBanners] = useState<BannerEntry[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    setBanners((current) => current.filter((banner) => banner.id !== id));
  }, []);

  const scheduleDismiss = useCallback(
    (id: string, duration: number | null) => {
      if (typeof window === "undefined" || !duration || duration <= 0) {
        return;
      }
      window.setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  const pushToast = useCallback(
    (options: ToastOptions): string => {
      const entry: ToastEntry = {
        kind: "toast",
        id: options.id ?? createNotificationId(),
        title: options.title,
        description: options.description,
        intent: options.intent ?? "info",
        actions: options.actions ?? [],
        duration: options.duration === undefined ? DEFAULT_TOAST_DURATION : options.duration,
        dismissible: options.dismissible ?? true,
        scope: options.scope,
        persistKey: options.persistKey,
        icon: options.icon,
        createdAt: Date.now(),
      };

      setToasts((current) => {
        const filtered = entry.persistKey
          ? current.filter((toast) => toast.persistKey !== entry.persistKey)
          : current;
        return [...filtered, entry];
      });

      scheduleDismiss(entry.id, entry.duration);
      return entry.id;
    },
    [scheduleDismiss],
  );

  const pushBanner = useCallback(
    (options: BannerOptions): string => {
      const entry: BannerEntry = {
        kind: "banner",
        id: options.id ?? createNotificationId(),
        title: options.title,
        description: options.description,
        intent: options.intent ?? "info",
        actions: options.actions ?? [],
        duration:
          options.duration === undefined
            ? options.sticky
              ? null
              : DEFAULT_BANNER_DURATION
            : options.duration,
        dismissible: options.dismissible ?? true,
        scope: options.scope,
        persistKey: options.persistKey,
        icon: options.icon,
        sticky: options.sticky ?? false,
        createdAt: Date.now(),
      };

      setBanners((current) => {
        const filtered = entry.persistKey
          ? current.filter((banner) => banner.persistKey !== entry.persistKey)
          : current;
        return [...filtered, entry];
      });

      scheduleDismiss(entry.id, entry.duration);
      return entry.id;
    },
    [scheduleDismiss],
  );

  const clearScope = useCallback((scope: string, kind?: "toast" | "banner") => {
    if (!scope) {
      return;
    }
    if (!kind || kind === "toast") {
      setToasts((current) => current.filter((toast) => toast.scope !== scope));
    }
    if (!kind || kind === "banner") {
      setBanners((current) => current.filter((banner) => banner.scope !== scope));
    }
  }, []);

  const contextValue = useMemo<NotificationsContextValue>(
    () => ({
      toasts,
      banners,
      pushToast,
      pushBanner,
      dismiss,
      clearScope,
    }),
    [toasts, banners, pushToast, pushBanner, dismiss, clearScope],
  );

  return (
    <NotificationsContext.Provider value={contextValue}>
      {children}
      <NotificationHost />
    </NotificationsContext.Provider>
  );
}

export function useNotificationsContext() {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error("useNotifications must be used within a NotificationsProvider");
  }
  return context;
}

function NotificationHost() {
  const { toasts, banners, dismiss } = useNotificationsContext();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => setIsMounted(true), []);

  const sortedBanners = useMemo(
    () => banners.slice().sort((a, b) => b.createdAt - a.createdAt),
    [banners],
  );
  const sortedToasts = useMemo(
    () => toasts.slice().sort((a, b) => b.createdAt - a.createdAt),
    [toasts],
  );

  if (!isMounted || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <>
      <div className="pointer-events-none fixed inset-x-0 top-0 z-[var(--app-z-toast)] flex justify-center px-4 pt-3 sm:justify-end sm:pr-6">
        {sortedBanners.length > 0 ? (
          <Stack
            side="bottom"
            itemCount={BANNER_STACK_COLLAPSED_COUNT}
            expandOnHover
            className="pointer-events-auto w-full max-w-sm"
          >
            {sortedBanners.map((banner) => (
              <StackItem key={banner.id}>
                <NotificationCard
                  entry={banner}
                  onDismiss={dismiss}
                  dismissOnAction={!banner.sticky}
                />
              </StackItem>
            ))}
          </Stack>
        ) : null}
      </div>
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[var(--app-z-toast)] flex justify-center px-4 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:justify-end sm:px-0">
        {sortedToasts.length > 0 ? (
          <Stack
            side="top"
            itemCount={TOAST_STACK_COLLAPSED_COUNT}
            expandOnHover
            className="pointer-events-auto w-full max-w-sm"
          >
            {sortedToasts.map((toast) => (
              <StackItem key={toast.id}>
                <NotificationCard entry={toast} onDismiss={dismiss} dismissOnAction />
              </StackItem>
            ))}
          </Stack>
        ) : null}
      </div>
    </>,
    document.body,
  );
}

function NotificationCard({
  entry,
  onDismiss,
  dismissOnAction,
}: {
  readonly entry: ToastEntry | BannerEntry;
  readonly onDismiss: (id: string) => void;
  readonly dismissOnAction: boolean;
}) {
  const intentStyle = INTENT_STYLES[entry.intent];

  return (
    <div className="flex items-start gap-3">
      <div className={cn("mt-0.5 flex h-8 w-8 items-center justify-center rounded-full", intentStyle.icon)}>
        {entry.icon ?? renderNotificationIcon(entry.intent)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold leading-snug text-foreground">{entry.title}</p>
        {entry.description ? (
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{entry.description}</p>
        ) : null}
        {entry.actions.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {entry.actions.map((action, index) => (
              <Button
                key={`${action.label}-${index}`}
                size="sm"
                variant={resolveActionVariant(action)}
                onClick={() => {
                  action.onSelect();
                  if (dismissOnAction) {
                    onDismiss(entry.id);
                  }
                }}
              >
                {action.label}
              </Button>
            ))}
          </div>
        ) : null}
      </div>
      {entry.dismissible ? (
        <button
          type="button"
          className="ml-2 inline-flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          aria-label="Dismiss notification"
          onClick={() => onDismiss(entry.id)}
        >
          <CloseIcon className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

function resolveActionVariant(action: NotificationAction) {
  switch (action.variant) {
    case "primary":
      return "default";
    case "ghost":
      return "ghost";
    case "secondary":
    default:
      return "secondary";
  }
}

function renderNotificationIcon(intent: NotificationIntent) {
  switch (intent) {
    case "success":
      return <SuccessIcon className="h-5 w-5" />;
    case "warning":
      return <WarningIcon className="h-5 w-5" />;
    case "danger":
      return <ErrorIcon className="h-5 w-5" />;
    default:
      return <InfoIcon className="h-5 w-5" />;
  }
}

const INTENT_STYLES: Record<NotificationIntent, { icon: string }> = {
  info: {
    icon: "bg-info/15 text-info",
  },
  success: {
    icon: "bg-success/15 text-success",
  },
  warning: {
    icon: "bg-warning/15 text-warning",
  },
  danger: {
    icon: "bg-destructive/15 text-destructive",
  },
};

function createNotificationId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}
