import clsx from "clsx";
import { useMemo } from "react";

const SIZE_STYLES = {
  xs: "h-6 w-6 text-[10px]",
  sm: "h-8 w-8 text-sm",
  md: "h-10 w-10 text-base",
  lg: "h-12 w-12 text-lg",
} as const;

export type AvatarSize = keyof typeof SIZE_STYLES;

export interface AvatarProps {
  readonly name?: string | null;
  readonly email?: string | null;
  readonly size?: AvatarSize;
  readonly className?: string;
}

function getInitials(name?: string | null, email?: string | null) {
  if (name && name.trim().length > 0) {
    const parts = name.trim().split(/\s+/u);
    const first = parts[0]?.[0];
    const last = parts[parts.length - 1]?.[0];
    if (first) {
      return `${first}${last ?? ""}`.toUpperCase();
    }
  }
  if (email && email.trim().length > 0) {
    return email.trim()[0]?.toUpperCase();
  }
  return "?";
}

export function Avatar({ name, email, size = "md", className }: AvatarProps) {
  const initials = useMemo(() => getInitials(name, email), [name, email]);

  return (
    <span
      aria-hidden="true"
      className={clsx(
        "inline-flex select-none items-center justify-center rounded-full bg-muted font-semibold text-foreground shadow-sm",
        SIZE_STYLES[size],
        className,
      )}
    >
      {initials}
    </span>
  );
}
