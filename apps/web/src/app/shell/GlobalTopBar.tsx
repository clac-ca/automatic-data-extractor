import { type FormEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";

export interface GlobalTopBarSearchProps {
  readonly id?: string;
  readonly value?: string;
  readonly defaultValue?: string;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly shortcutHint?: string;
  readonly enableShortcut?: boolean;
  readonly onChange?: (value: string) => void;
  readonly onSubmit?: (value: string) => void;
}

interface GlobalTopBarProps {
  readonly brand?: ReactNode;
  readonly leading?: ReactNode;
  readonly actions?: ReactNode;
  readonly trailing?: ReactNode;
  readonly search?: GlobalTopBarSearchProps;
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
  const generatedSearchId = useId();
  const searchInputRef = useRef<HTMLInputElement>(null);
  const isSearchControlled = search?.value !== undefined;
  const defaultSearchValue = search?.defaultValue ?? "";
  const [uncontrolledQuery, setUncontrolledQuery] = useState(defaultSearchValue);
  const showSearch = Boolean(search);
  const enableShortcut = search?.enableShortcut ?? true;

  useEffect(() => {
    if (!showSearch || isSearchControlled) {
      return;
    }
    setUncontrolledQuery(defaultSearchValue);
  }, [showSearch, isSearchControlled, defaultSearchValue]);

  useEffect(() => {
    if (!showSearch || !enableShortcut) {
      return;
    }
    if (typeof window === "undefined") {
      return;
    }
    const handleKeydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [showSearch, enableShortcut]);

  const searchQuery = search?.value ?? uncontrolledQuery;
  const searchPlaceholder = search?.placeholder ?? "Search everything…";
  const searchAriaLabel = search?.ariaLabel ?? searchPlaceholder;
  const searchShortcutHint = search?.shortcutHint ?? "⌘K";

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchQuery.trim();
    if (!query && !search?.onSubmit) {
      return;
    }
    search?.onSubmit?.(query);
  };

  const handleSearchChange = (next: string) => {
    if (!isSearchControlled) {
      setUncontrolledQuery(next);
    }
    search?.onChange?.(next);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-white/70 bg-white/85 backdrop-blur supports-[backdrop-filter]:backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <div
          className={clsx(
            "flex min-h-[3.5rem] flex-wrap items-center gap-3",
            showSearch && "lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center lg:gap-8",
          )}
        >
          <div className="flex min-w-0 items-center gap-3">
            {brand}
            {leading}
          </div>
          {showSearch ? (
            <div className="order-last w-full lg:order-none lg:max-w-2xl lg:justify-self-center">
              <form
                className="flex w-full items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/90 px-3 py-2 text-sm text-slate-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] transition focus-within:border-brand-200 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-100"
                role="search"
                aria-label={searchAriaLabel}
                onSubmit={handleSearchSubmit}
              >
                <label htmlFor={search?.id ?? generatedSearchId} className="sr-only">
                  {searchAriaLabel}
                </label>
                <SearchIcon />
                <input
                  ref={searchInputRef}
                  id={search?.id ?? generatedSearchId}
                  type="search"
                  value={searchQuery}
                  onChange={(event) => handleSearchChange(event.target.value)}
                  placeholder={searchPlaceholder}
                  className="w-full border-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
                />
                <span className="hidden text-xs font-semibold text-slate-400 sm:inline">{searchShortcutHint}</span>
              </form>
            </div>
          ) : null}
          <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
            {actions}
            {trailing}
          </div>
        </div>
        {secondaryContent ? <div className="flex flex-wrap items-center gap-2">{secondaryContent}</div> : null}
      </div>
    </header>
  );
}

function SearchIcon() {
  return (
    <svg className="h-4 w-4 flex-shrink-0 text-slate-400" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx="9" cy="9" r="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m13.5 13.5 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
