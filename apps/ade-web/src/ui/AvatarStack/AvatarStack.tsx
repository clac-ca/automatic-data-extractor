import clsx from "clsx";

import { Avatar, type AvatarSize } from "@ui/Avatar";

export type AvatarStackItem = {
  id: string;
  name?: string | null;
  email?: string | null;
};

const SIZE_STYLES: Record<AvatarSize, string> = {
  xs: "h-6 w-6 text-[10px]",
  sm: "h-8 w-8 text-sm",
  md: "h-10 w-10 text-base",
  lg: "h-12 w-12 text-lg",
};

export function AvatarStack({
  items,
  size = "sm",
  max = 3,
  className,
}: {
  items: AvatarStackItem[];
  size?: AvatarSize;
  max?: number;
  className?: string;
}) {
  const visible = items.slice(0, Math.max(0, max));
  const overflow = Math.max(0, items.length - visible.length);

  return (
    <div className={clsx("flex items-center -space-x-2", className)}>
      {visible.map((item) => {
        const label = item.name || item.email || "Participant";
        return (
          <span key={item.id} title={label} className="rounded-full ring-2 ring-background">
            <Avatar name={item.name} email={item.email} size={size} />
          </span>
        );
      })}
      {overflow > 0 ? (
        <span
          className={clsx(
            "flex items-center justify-center rounded-full border border-border bg-muted font-semibold text-muted-foreground ring-2 ring-background",
            SIZE_STYLES[size],
          )}
        >
          +{overflow}
        </span>
      ) : null}
    </div>
  );
}
