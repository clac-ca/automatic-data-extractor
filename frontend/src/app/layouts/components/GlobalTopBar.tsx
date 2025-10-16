import type { ReactNode } from "react";
import clsx from "clsx";

interface GlobalTopBarProps {
  readonly start: ReactNode;
  readonly center?: ReactNode;
  readonly end: ReactNode;
  readonly className?: string;
  readonly maxWidthClassName?: string;
}

export function GlobalTopBar({ start, center, end, className, maxWidthClassName }: GlobalTopBarProps) {
  return (
    <header className={clsx("sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur", className)}>
      <div
        className={clsx(
          "mx-auto flex w-full flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:gap-4",
          maxWidthClassName ?? "max-w-7xl",
        )}
      >
        <div className="flex w-full items-center gap-3">
          <div className="flex min-w-0 items-center gap-3 md:flex-1">{start}</div>
          {center ? <div className="hidden flex-1 items-center justify-center md:flex">{center}</div> : null}
          <div className={clsx("ml-auto flex flex-shrink-0 items-center gap-2", center ? "md:ml-0" : "")}>{end}</div>
        </div>
        {center ? <div className="md:hidden">{center}</div> : null}
      </div>
    </header>
  );
}
