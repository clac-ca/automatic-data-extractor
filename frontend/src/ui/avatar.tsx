import clsx from "clsx";
import { useMemo } from "react";

const SIZE_STYLES = {
  sm: "h-8 w-8 text-sm",
  md: "h-10 w-10 text-base",
  lg: "h-12 w-12 text-lg",
} as const;

type AvatarSize = keyof typeof SIZE_STYLES;

interface AvatarProps {
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
        "inline-flex select-none items-center justify-center rounded-full bg-gradient-to-br from-brand-100 via-brand-200 to-brand-300 font-semibold text-brand-900 shadow-sm",
        SIZE_STYLES[size],
        className,
      )}
    >
      {initials}
    </span>
  );
}
