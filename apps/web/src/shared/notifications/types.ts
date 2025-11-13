import type { ReactNode } from "react";

export type NotificationIntent = "info" | "success" | "warning" | "danger";

export interface NotificationAction {
  readonly label: string;
  readonly onSelect: () => void;
  readonly variant?: "primary" | "secondary" | "ghost";
}

interface NotificationBase {
  readonly id?: string;
  readonly title: string;
  readonly description?: string;
  readonly intent?: NotificationIntent;
  readonly dismissible?: boolean;
  readonly actions?: readonly NotificationAction[];
  readonly duration?: number | null;
  readonly scope?: string;
  readonly persistKey?: string;
  readonly icon?: ReactNode;
}

export interface ToastOptions extends NotificationBase {
  readonly kind?: "toast";
}

export interface BannerOptions extends NotificationBase {
  readonly kind?: "banner";
  readonly sticky?: boolean;
}

