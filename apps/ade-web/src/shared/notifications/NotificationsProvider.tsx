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
import clsx from "clsx";

import type { BannerOptions, NotificationAction, NotificationIntent, ToastOptions } from "./types";

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
const MAX_VISIBLE_TOASTS = 4;

export function NotificationsProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const [banners, setBanners] = useState<BannerEntry[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    setBanners((current) => current.filter((banner) => banner.id !== id));
  }, []);

  const pushToast = useCallback((options: ToastOptions): string => {
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
      const next = [...filtered, entry];
      return next.length > MAX_VISIBLE_TOASTS ? next.slice(next.length - MAX_VISIBLE_TOASTS) : next;
    });
    if (typeof window !== "undefined" && entry.duration && entry.duration > 0) {
      window.setTimeout(() => dismiss(entry.id), entry.duration + 50);
    }
    return entry.id;
  }, [dismiss]);

  const pushBanner = useCallback((options: BannerOptions): string => {
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
    if (typeof window !== "undefined" && entry.duration && entry.duration > 0) {
      window.setTimeout(() => dismiss(entry.id), entry.duration + 50);
    }
    return entry.id;
  }, [dismiss]);

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
  if (!isMounted || typeof document === "undefined") {
    return null;
  }
  return createPortal(
    <>
      <div className="pointer-events-none fixed inset-x-0 top-0 z-[205] flex flex-col items-center gap-3 px-4 pt-3 sm:items-end sm:pr-6">
        {banners
          .slice()
          .sort((a, b) => a.createdAt - b.createdAt)
          .map((banner) => (
            <BannerCard key={banner.id} banner={banner} onDismiss={dismiss} />
          ))}
      </div>
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[210] flex flex-col items-center gap-3 px-4 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:items-end sm:px-0">
        {toasts
          .slice()
          .sort((a, b) => a.createdAt - b.createdAt)
          .map((toast) => (
            <ToastCard key={toast.id} toast={toast} onDismiss={dismiss} />
          ))}
      </div>
    </>,
    document.body,
  );
}

function ToastCard({ toast, onDismiss }: { readonly toast: ToastEntry; readonly onDismiss: (id: string) => void }) {
  const autoDismiss = toast.duration !== null && toast.duration > 0;
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!autoDismiss || !toast.duration) {
      return;
    }
    setProgress(100);
    const frame = requestAnimationFrame(() => setProgress(0));
    const timeout = window.setTimeout(() => onDismiss(toast.id), toast.duration);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timeout);
    };
  }, [autoDismiss, toast.duration, toast.id, onDismiss]);

  const intentTheme = TOAST_THEMES[toast.intent];

  return (
    <div
      className={clsx(
        "pointer-events-auto w-full max-w-sm rounded-2xl border px-4 py-3 text-sm shadow-2xl backdrop-blur",
        intentTheme.container,
        intentTheme.border,
      )}
    >
      <div className="flex gap-3">
        <div className={clsx("mt-1 flex h-8 w-8 items-center justify-center rounded-full", intentTheme.icon)}>
          {toast.icon ?? renderNotificationIcon(toast.intent)}
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="text-sm font-semibold leading-snug text-white">{toast.title}</p>
          {toast.description ? (
            <p className="mt-1 text-xs leading-relaxed text-white/70">{toast.description}</p>
          ) : null}
          {toast.actions.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {toast.actions.map((action) => (
                <NotificationActionButton
                  key={action.label}
                  action={action}
                  onPress={() => {
                    action.onSelect();
                    onDismiss(toast.id);
                  }}
                  appearance="dark"
                />
              ))}
            </div>
          ) : null}
        </div>
        {toast.dismissible ? (
          <button
            type="button"
            className="ml-2 inline-flex h-8 w-8 items-center justify-center rounded-full text-white/60 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
            aria-label="Dismiss notification"
            onClick={() => onDismiss(toast.id)}
          >
            <CloseIcon />
          </button>
        ) : null}
      </div>
      {autoDismiss && toast.duration ? (
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/10">
          <div
            className={clsx("h-full rounded-full", intentTheme.progress)}
            style={{ width: `${progress}%`, transition: `width ${toast.duration}ms linear` }}
          />
        </div>
      ) : null}
    </div>
  );
}

function BannerCard({ banner, onDismiss }: { readonly banner: BannerEntry; readonly onDismiss: (id: string) => void }) {
  const autoDismiss = !banner.sticky && banner.duration !== null && banner.duration > 0;
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!autoDismiss || !banner.duration) {
      return;
    }
    setProgress(100);
    const frame = requestAnimationFrame(() => setProgress(0));
    const timeout = window.setTimeout(() => onDismiss(banner.id), banner.duration);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timeout);
    };
  }, [autoDismiss, banner.duration, banner.id, onDismiss]);

  const theme = BANNER_THEMES[banner.intent];

  return (
    <div
      className={clsx(
        "pointer-events-auto w-full max-w-sm rounded-lg border px-3.5 py-2.5 shadow-lg shadow-black/30 backdrop-blur-sm sm:min-w-[300px]",
        theme.container,
        theme.border,
      )}
    >
      <div className="flex items-start gap-3">
        <div className={clsx("flex h-7 w-7 items-center justify-center rounded-full text-base", theme.icon)}>
          {banner.icon ?? renderNotificationIcon(banner.intent)}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="text-[13px] font-semibold leading-tight">{banner.title}</p>
          {banner.description ? (
            <p className="text-[12px] leading-relaxed text-white/75">{banner.description}</p>
          ) : null}
          {banner.actions.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {banner.actions.map((action) => (
                <NotificationActionButton
                  key={action.label}
                  action={action}
                  onPress={() => {
                    action.onSelect();
                    if (!banner.sticky) {
                      onDismiss(banner.id);
                    }
                  }}
                  appearance="light"
                />
              ))}
            </div>
          ) : null}
        </div>
        {banner.dismissible ? (
          <button
            type="button"
            className={clsx(
              "ml-2 inline-flex h-7 w-7 items-center justify-center rounded-full text-white/70 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30",
              theme.dismiss,
            )}
            aria-label="Dismiss notification"
            onClick={() => onDismiss(banner.id)}
          >
            <CloseIcon />
          </button>
        ) : null}
      </div>
      {autoDismiss && banner.duration ? (
        <div className="mt-2 h-0.5 overflow-hidden rounded-full bg-white/10">
          <div
            className={clsx("h-full rounded-full", theme.progress)}
            style={{ width: `${progress}%`, transition: `width ${banner.duration}ms linear` }}
          />
        </div>
      ) : null}
    </div>
  );
}

function NotificationActionButton({
  action,
  onPress,
  appearance,
}: {
  readonly action: NotificationAction;
  readonly onPress: () => void;
  readonly appearance: "light" | "dark";
}) {
  const variant = action.variant ?? "secondary";
  const base =
    appearance === "dark"
      ? "border-white/15 text-white/90 hover:bg-white/10 focus-visible:ring-white/30"
      : "border-white/20 text-white hover:bg-white/10 focus-visible:ring-white/30";
  const primary =
    appearance === "dark"
      ? "bg-white text-slate-900 hover:bg-slate-100 focus-visible:ring-white/40"
      : "bg-white text-slate-900 hover:bg-slate-100 focus-visible:ring-white/40";
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center justify-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide transition focus-visible:outline-none focus-visible:ring-2",
        variant === "primary" ? primary : base,
      )}
      onClick={onPress}
    >
      {action.label}
    </button>
  );
}

function renderNotificationIcon(intent: NotificationIntent) {
  switch (intent) {
    case "success":
      return <SuccessIcon />;
    case "warning":
      return <WarningIcon />;
    case "danger":
      return <ErrorIcon />;
    default:
      return <InfoIcon />;
  }
}

const TOAST_THEMES: Record<
  NotificationIntent,
  { container: string; border: string; icon: string; progress: string }
> = {
  info: {
    container: "bg-[#0b1220]/95 text-white",
    border: "border-white/5",
    icon: "bg-sky-500/15 text-sky-200",
    progress: "bg-gradient-to-r from-sky-500 to-blue-400",
  },
  success: {
    container: "bg-[#031b16]/95 text-emerald-50",
    border: "border-emerald-500/20",
    icon: "bg-emerald-500/15 text-emerald-200",
    progress: "bg-gradient-to-r from-emerald-400 to-lime-400",
  },
  warning: {
    container: "bg-[#211604]/95 text-amber-50",
    border: "border-amber-500/25",
    icon: "bg-amber-400/20 text-amber-100",
    progress: "bg-gradient-to-r from-amber-400 to-orange-400",
  },
  danger: {
    container: "bg-[#22060b]/95 text-rose-50",
    border: "border-rose-500/30",
    icon: "bg-rose-500/15 text-rose-100",
    progress: "bg-gradient-to-r from-rose-500 to-rose-400",
  },
};

const BANNER_THEMES: Record<
  NotificationIntent,
  { container: string; border: string; icon: string; progress: string; dismiss: string }
> = {
  info: {
    container: "bg-[#101828]/85 text-white",
    border: "border-white/10",
    icon: "bg-sky-500/15 text-sky-200",
    progress: "bg-gradient-to-r from-sky-500 to-blue-400",
    dismiss: "hover:bg-white/10",
  },
  success: {
    container: "bg-[#0d1c17]/85 text-emerald-50",
    border: "border-emerald-500/15",
    icon: "bg-emerald-500/15 text-emerald-200",
    progress: "bg-gradient-to-r from-emerald-400 to-lime-400",
    dismiss: "hover:bg-white/10",
  },
  warning: {
    container: "bg-[#1b1507]/85 text-amber-50",
    border: "border-amber-500/25",
    icon: "bg-amber-500/15 text-amber-100",
    progress: "bg-gradient-to-r from-amber-400 to-orange-400",
    dismiss: "hover:bg-white/10",
  },
  danger: {
    container: "bg-[#200912]/85 text-rose-50",
    border: "border-rose-500/25",
    icon: "bg-rose-500/15 text-rose-100",
    progress: "bg-gradient-to-r from-rose-500 to-rose-400",
    dismiss: "hover:bg-white/10",
  },
};

function createNotificationId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

function InfoIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.6" opacity={0.8} />
      <path d="M10 7.5v.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M9.2 9.5h1.6V14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.6" opacity={0.8} />
      <path d="M6.5 10.5l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M9 4.6l-6 10.4a1 1 0 0 0 .87 1.5h12.26a1 1 0 0 0 .87-1.5L11 4.6a1 1 0 0 0-1.74 0Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 8v3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M10 14h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.6" opacity={0.8} />
      <path d="M7 7l6 6m0-6-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 4l8 8m0-8-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
