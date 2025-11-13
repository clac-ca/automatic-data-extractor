import type { ReactNode } from "react";
import clsx from "clsx";

interface GlobalTopBarProps {
  readonly leading?: ReactNode;
  readonly center?: ReactNode;
  readonly trailing?: ReactNode;
}

export function GlobalTopBar({ leading, center, trailing }: GlobalTopBarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-white/60 bg-gradient-to-r from-white/95 via-slate-50/95 to-white/90 shadow-[0_20px_45px_-30px_rgba(15,23,42,0.75)] backdrop-blur supports-[backdrop-filter]:backdrop-blur-xl">
      <div
        className={clsx(
          "flex min-h-[4.25rem] w-full flex-wrap items-center gap-4 px-4 py-3 sm:px-6 lg:px-10",
          center && "lg:grid lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:items-center lg:gap-6",
        )}
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">{leading}</div>
        {center ? (
          <div className="hidden min-w-0 items-center justify-center md:flex">{center}</div>
        ) : null}
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">{trailing}</div>
      </div>
    </header>
  );
}
