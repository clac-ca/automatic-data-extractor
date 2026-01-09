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
          "w-full col-span-2 row-start-2 xl:col-span-1 xl:row-start-1 xl:col-start-2 xl:justify-self-center xl:max-w-[42rem]",
          search.className,
        ),
      }
    : undefined;

  return (
    <header
      className={clsx(
        "sticky top-0 z-50",
        "border-b border-border/70",
        "bg-background/80 text-foreground backdrop-blur",
        "transition-shadow duration-200 motion-reduce:transition-none",
        isScrolled ? "shadow-[0_12px_40px_-30px_rgb(0_0_0_/_0.45)]" : "shadow-none",
      )}
      role="banner"
    >
      {/* Skip link (small detail, big polish for keyboard users) */}
      <a
        href="#main-content"
        className={clsx(
          "sr-only",
          "focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[60]",
          "rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground shadow",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
        )}
      >
        Skip to content
      </a>

      <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <div
          className={clsx(
            "grid min-h-[3.5rem] w-full items-center gap-3 sm:gap-4",
            showSearch
              ? "grid-cols-[minmax(0,1fr)_auto] xl:grid-cols-[auto_minmax(0,1fr)_auto] xl:gap-8"
              : "grid-cols-[minmax(0,1fr)_auto]",
          )}
        >
          <div className="col-start-1 row-start-1 flex w-full min-w-0 items-center gap-3">
            {brand}
            {leading}
          </div>

          {searchProps ? <GlobalSearchField {...searchProps} /> : null}

          <div
            className={clsx(
              "col-start-2 row-start-1 flex flex-wrap items-center justify-end gap-2",
              showSearch && "xl:col-start-3 xl:row-start-1",
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
