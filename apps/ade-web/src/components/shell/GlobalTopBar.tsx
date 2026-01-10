import { type ReactNode, useEffect, useState } from "react";
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
  readonly scrollContainer?: HTMLElement | null;
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
  scrollContainer,
}: GlobalTopBarProps) {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let ticking = false;
    const target = scrollContainer ?? window;
    const readScrollTop = () => (target === window ? window.scrollY : (target as HTMLElement).scrollTop);

    const update = () => {
      ticking = false;
      const next = readScrollTop() > 0;
      setIsScrolled((prev) => (prev === next ? prev : next));
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    };

    update();
    target.addEventListener("scroll", onScroll, { passive: true });
    return () => target.removeEventListener("scroll", onScroll);
  }, [scrollContainer]);

  const showSearch = Boolean(search);

  const searchProps = search
    ? {
        ...search,
        // Default to a top-bar-friendly look unless caller overrides.
        variant: search.variant ?? "header",
        className: clsx(
          "w-full min-w-0 justify-self-center",
          search.className,
        ),
      }
    : undefined;

  return (
    <header
      className={clsx(
        "sticky top-0 z-[var(--app-z-header)] relative",
        "border-b border-border/60",
        "bg-card/80 text-foreground backdrop-blur-md",
        "bg-gradient-to-r from-card/90 via-accent/45 to-card/90",
        "transition-[box-shadow,background-color] duration-200 motion-reduce:transition-none",
        isScrolled ? "shadow-md" : "shadow-sm",
      )}
      role="banner"
    >
      {/* Skip link (small detail, big polish for keyboard users) */}
      <a
        href="#main-content"
        className={clsx(
          "sr-only",
          "focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[var(--app-z-popover)]",
          "rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground shadow",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
        )}
      >
        Skip to content
      </a>

      <div className="relative z-10 flex flex-col gap-2 px-4 sm:px-6 lg:px-10">
        <div
          className={clsx(
            "grid h-[var(--app-shell-header-h)] w-full items-center gap-3 sm:gap-4",
            showSearch
              ? "grid-cols-[auto_minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_minmax(0,var(--app-shell-search-max-w))_auto] lg:gap-8"
              : "grid-cols-[minmax(0,1fr)_auto]",
          )}
        >
          <div className="flex min-w-0 items-center gap-3">
            {brand}
            {leading}
          </div>

          {searchProps ? <GlobalSearchField {...searchProps} /> : null}

          <div
            className={clsx(
              "flex min-w-0 flex-nowrap items-center justify-end gap-2",
            )}
          >
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
