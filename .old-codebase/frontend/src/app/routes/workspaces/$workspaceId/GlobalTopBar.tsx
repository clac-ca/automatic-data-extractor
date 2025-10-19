import type { ReactNode } from "react";
import clsx from "clsx";

export interface GlobalTopBarProps {
  readonly leading?: ReactNode;
  readonly center?: ReactNode;
  readonly trailing?: ReactNode;
  readonly maxWidthClassName?: string;
}

export function GlobalTopBar({
  leading,
  center,
  trailing,
  maxWidthClassName = "max-w-7xl",
}: GlobalTopBarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div
        className={clsx(
          "mx-auto flex h-16 w-full items-center gap-4 px-4 sm:px-6",
          maxWidthClassName,
        )}
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">{leading}</div>
        {center ? (
          <div className="hidden min-w-0 flex-1 items-center justify-center md:flex">{center}</div>
        ) : null}
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">{trailing}</div>
      </div>
    </header>
  );
}
