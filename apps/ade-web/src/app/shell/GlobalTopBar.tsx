import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
import clsx from "clsx";

import { GlobalSearchField, type GlobalSearchFieldProps } from "./GlobalSearchField";

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

/**
 * Polished “app shell” top bar:
 * - sticky, lightweight, with subtle elevation once content scrolls underneath
 * - predictable layout: left (brand/primary), center (search), right (utility/actions)
 * - z-index above overlay sidebars
 */
export function GlobalTopBar({
  brand,
  leading,
  actions,
  trailing,
  search,
  secondaryContent,
}: GlobalTopBarProps) {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let ticking = false;

    const update = () => {
      ticking = false;
      const next = window.scrollY > 0;
      setIsScrolled((prev) => (prev === next ? prev : next));
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const showSearch = Boolean(search);

  const searchProps = search
    ? {
        ...search,
        // Default to a top-bar-friendly look unless caller overrides.
        variant: search.variant ?? "minimal",
        className: clsx("order-last w-full lg:order-none", search.className),
      }
    : undefined;

  return (
    <header
      className={clsx(
        "sticky top-0 z-50",
        "border-b border-header-border",
        "bg-header text-header-foreground",
        "transition-shadow duration-200 motion-reduce:transition-none",
        isScrolled ? "shadow-[0_12px_40px_-30px_rgb(var(--sys-color-shadow)/0.45)]" : "shadow-none",
      )}
      style={{ "--focus-ring-offset": "rgb(var(--sys-color-header-bg) / 1)" } as CSSProperties}
      role="banner"
    >
      {/* Skip link (small detail, big polish for keyboard users) */}
      <a
        href="#main-content"
        className={clsx(
          "sr-only",
          "focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[60]",
          "rounded-lg border border-header-border bg-card px-3 py-2 text-sm font-semibold text-foreground shadow",
          "focus:outline-none focus:ring-2 focus:ring-header-ring focus:ring-offset-2 focus:ring-offset-header",
        )}
      >
        Skip to content
      </a>

      <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <div
          className={clsx(
            "flex min-h-[3.5rem] w-full flex-wrap items-center gap-3 sm:gap-4",
            showSearch
              ? // Center search stays visually centered and stable.
                "lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,42rem)_minmax(0,1fr)] lg:items-center lg:gap-8"
              : "justify-between",
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

        {secondaryContent ? (
          <div className="flex flex-wrap items-center gap-2">{secondaryContent}</div>
        ) : null}
      </div>
    </header>
  );
}
