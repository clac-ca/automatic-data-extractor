import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";

export interface GlobalSearchSuggestion {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly action?: () => void;
}

export interface GlobalTopBarSearchProps {
  readonly id?: string;
  readonly value?: string;
  readonly defaultValue?: string;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly shortcutHint?: string;
  readonly enableShortcut?: boolean;
  readonly scopeLabel?: string;
  readonly leadingIcon?: ReactNode;
  readonly onChange?: (value: string) => void;
  readonly onSubmit?: (value: string) => void;
  readonly suggestions?: readonly GlobalSearchSuggestion[];
  readonly onSelectSuggestion?: (suggestion: GlobalSearchSuggestion) => void;
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
  const controlledSearchValue = search?.value;
  const defaultSearchValue = search?.defaultValue ?? "";
  const [uncontrolledQuery, setUncontrolledQuery] = useState(defaultSearchValue);
  const showSearch = Boolean(search);
  const enableShortcut = search?.enableShortcut ?? true;
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState(0);
  const suggestions = search?.suggestions ?? [];
  const scopeLabel = search?.scopeLabel;
  const defaultSearchIcon = (
    <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-white/90 text-brand-600 shadow-inner shadow-white/60 ring-1 ring-inset ring-white/70 sm:h-10 sm:w-10 sm:rounded-xl">
      <SearchIcon className="h-4 w-4 flex-shrink-0 text-brand-600" />
    </span>
  );
  const searchLeadingIcon = search?.leadingIcon ?? defaultSearchIcon;

  useEffect(() => {
    if (!showSearch || isSearchControlled) {
      return;
    }
    setUncontrolledQuery(defaultSearchValue);
  }, [showSearch, isSearchControlled, defaultSearchValue]);

  useEffect(() => {
    setHighlightedSuggestion(0);
  }, [suggestions.length, controlledSearchValue, defaultSearchValue]);

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
  const showSuggestions = showSearch && isSearchFocused && suggestions.length > 0;

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

  const handleSuggestionSelection = (suggestion?: GlobalSearchSuggestion) => {
    if (!suggestion) {
      return;
    }
    search?.onSelectSuggestion?.(suggestion);
    suggestion.action?.();
    setIsSearchFocused(false);
    searchInputRef.current?.blur();
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions) {
      if (event.key === "Escape") {
        setIsSearchFocused(false);
        event.currentTarget.blur();
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedSuggestion((current) => (current + 1) % suggestions.length);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedSuggestion((current) => (current - 1 + suggestions.length) % suggestions.length);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      handleSuggestionSelection(suggestions[highlightedSuggestion]);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setIsSearchFocused(false);
      event.currentTarget.blur();
    }
  };

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
          {showSearch ? (
            <div className="relative order-last w-full lg:order-none lg:max-w-2xl lg:justify-self-center">
              <div
                className={clsx(
                  "group/search overflow-hidden rounded-xl border border-slate-200/70 bg-gradient-to-r from-white/95 via-slate-50/80 to-white/95 shadow-[0_20px_45px_-30px_rgba(15,23,42,0.65)] ring-1 ring-inset ring-white/80 transition focus-within:border-brand-200 focus-within:shadow-[0_25px_55px_-35px_rgba(79,70,229,0.55)] sm:rounded-2xl",
                  showSuggestions && "focus-within:shadow-[0_35px_80px_-40px_rgba(79,70,229,0.55)]",
                )}
              >
                <form
                  className="flex w-full items-center gap-3 px-4 py-2 text-sm text-slate-600 sm:px-5 sm:py-2.5"
                  role="search"
                  aria-label={searchAriaLabel}
                  onSubmit={handleSearchSubmit}
                >
                  <label htmlFor={search?.id ?? generatedSearchId} className="sr-only">
                    {searchAriaLabel}
                  </label>
                  {searchLeadingIcon}
                  <div className="flex min-w-0 flex-1 flex-col">
                    {scopeLabel ? (
                      <span className="text-[0.6rem] font-semibold uppercase tracking-wide text-slate-400 sm:text-[0.65rem]">
                        {scopeLabel}
                      </span>
                    ) : null}
                    <input
                      ref={searchInputRef}
                      id={search?.id ?? generatedSearchId}
                      type="search"
                      value={searchQuery}
                      onChange={(event) => handleSearchChange(event.target.value)}
                      onFocus={() => setIsSearchFocused(true)}
                      onBlur={() => setIsSearchFocused(false)}
                      onKeyDown={handleSearchKeyDown}
                      placeholder={searchPlaceholder}
                      className="w-full border-0 bg-transparent text-base font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none"
                    />
                  </div>
                  <span className="hidden items-center gap-1 rounded-full border border-slate-200/80 bg-white/80 px-2 py-1 text-xs font-semibold text-slate-500 shadow-inner shadow-white/60 md:inline-flex">
                    {searchShortcutHint}
                  </span>
                </form>
                {showSuggestions ? (
                  <div className="border-t border-slate-200/70 bg-white/95">
                    <ul role="listbox" aria-label="Search suggestions" className="divide-y divide-slate-100/80">
                      {suggestions.map((suggestion, index) => (
                        <li key={suggestion.id}>
                          <button
                            type="button"
                            role="option"
                            aria-selected={index === highlightedSuggestion}
                            onMouseEnter={() => setHighlightedSuggestion(index)}
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => handleSuggestionSelection(suggestion)}
                            className={clsx(
                              "flex w-full items-start gap-3 px-5 py-3 text-left transition",
                              index === highlightedSuggestion ? "bg-brand-50/60" : "hover:bg-slate-50/80",
                            )}
                          >
                            {suggestion.icon ? (
                              <span className="mt-0.5 text-slate-400">{suggestion.icon}</span>
                            ) : (
                              <span className="mt-1 h-2.5 w-2.5 rounded-full bg-slate-200" aria-hidden />
                            )}
                            <span className="flex min-w-0 flex-col">
                              <span className="text-sm font-semibold text-slate-900">{suggestion.label}</span>
                              {suggestion.description ? (
                                <span className="text-xs text-slate-500">{suggestion.description}</span>
                              ) : null}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
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

function SearchIcon({ className = "h-4 w-4 flex-shrink-0 text-slate-400" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx="9" cy="9" r="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m13.5 13.5 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
