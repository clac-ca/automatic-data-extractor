import { type ReactNode } from "react";
import clsx from "clsx";

import {
  GlobalSearchField,
  type GlobalSearchFieldProps,
} from "./GlobalSearchField";

export type {
  GlobalSearchFilter,
  GlobalSearchFieldProps as GlobalTopBarSearchProps,
  GlobalSearchSuggestion,
} from "./GlobalSearchField";

interface GlobalTopBarProps {
  readonly brand?: ReactNode;
  readonly leading?: ReactNode;
  readonly actions?: ReactNode;
  readonly trailing?: ReactNode;
  readonly search?: GlobalSearchFieldProps;
  readonly secondaryContent?: ReactNode;
}

export function GlobalTopBar({
  brand,
  leading,
  actions,
  trailing,
  search,
  secondaryContent,
}: GlobalTopBarProps) {
  const showSearch = Boolean(search);
  const searchProps = search
    ? {
        ...search,
        className: clsx(
          "order-last w-full lg:order-none lg:max-w-2xl lg:justify-self-center",
          search.className,
        ),
      }
    : undefined;

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-gradient-to-b from-white/95 via-slate-50/70 to-white/90 shadow-[0_12px_40px_-30px_rgba(15,23,42,0.8)] backdrop-blur supports-[backdrop-filter]:backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <div
          className={clsx(
            "flex min-h-[3.5rem] w-full flex-wrap items-center gap-3 sm:gap-4",
            showSearch ? "lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center lg:gap-8" : "justify-between",
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-3 lg:flex-none">
            {brand}
            {leading}
          </div>
          {searchProps ? <GlobalSearchField {...searchProps} /> : null}
          <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-none">
            {actions}
            {trailing}
          </div>
        </div>
        {secondaryContent ? <div className="flex flex-wrap items-center gap-2">{secondaryContent}</div> : null}
      </div>
    </header>
  );
}
