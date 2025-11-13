import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import clsx from "clsx";

export interface GlobalSearchSuggestion {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly action?: () => void;
  readonly shortcutHint?: string;
}

export interface GlobalSearchFilter {
  readonly id: string;
  readonly label: string;
  readonly active?: boolean;
}

export type GlobalSearchFieldVariant = "default" | "minimal";

export interface GlobalSearchFieldProps {
  readonly id?: string;
  readonly value?: string;
  readonly defaultValue?: string;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly shortcutHint?: string;
  readonly shortcutKey?: string;
  readonly enableShortcut?: boolean;
  readonly scopeLabel?: string;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
  readonly className?: string;
  readonly variant?: GlobalSearchFieldVariant;
  readonly isLoading?: boolean;
  readonly loadingLabel?: string;
  readonly filters?: readonly GlobalSearchFilter[];
  readonly onSelectFilter?: (filter: GlobalSearchFilter) => void;
  readonly emptyState?: ReactNode;
  readonly onChange?: (value: string) => void;
  readonly onSubmit?: (value: string) => void;
  readonly onClear?: () => void;
  readonly onFocus?: () => void;
  readonly onBlur?: () => void;
  readonly suggestions?: readonly GlobalSearchSuggestion[];
  readonly onSelectSuggestion?: (suggestion: GlobalSearchSuggestion) => void;
  readonly renderSuggestion?: (args: { suggestion: GlobalSearchSuggestion; active: boolean }) => ReactNode;
}

export function GlobalSearchField({
  id,
  value,
  defaultValue = "",
  placeholder = "Search…",
  ariaLabel,
  shortcutHint = "⌘K",
  shortcutKey = "k",
  enableShortcut = true,
  scopeLabel,
  leadingIcon,
  trailingIcon,
  className,
  variant = "default",
  isLoading = false,
  loadingLabel = "Loading suggestions",
  filters,
  onSelectFilter,
  emptyState,
  onChange,
  onSubmit,
  onClear,
  onFocus,
  onBlur,
  suggestions = [],
  onSelectSuggestion,
  renderSuggestion,
}: GlobalSearchFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const suggestionsListId = `${generatedId}-suggestions`;
  const searchInputRef = useRef<HTMLInputElement>(null);
  const isControlled = value !== undefined;
  const [uncontrolledQuery, setUncontrolledQuery] = useState(defaultValue);
  const [isFocused, setIsFocused] = useState(false);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState(0);
  const query = isControlled ? value ?? "" : uncontrolledQuery;
  const hasSuggestions = suggestions.length > 0;
  const hasFilters = Boolean(filters?.length);
  const showDropdown = isFocused && (hasSuggestions || isLoading || Boolean(emptyState) || hasFilters);
  const showEmptyState = isFocused && !hasSuggestions && !isLoading && Boolean(emptyState);
  const canClear = Boolean(onClear || !isControlled);
  const shortcutLabel = shortcutHint || "⌘K";
  const searchAriaLabel = ariaLabel ?? placeholder;

  useEffect(() => {
    if (!isControlled) {
      setUncontrolledQuery(defaultValue);
    }
  }, [defaultValue, isControlled]);

  useEffect(() => {
    setHighlightedSuggestion(0);
  }, [suggestions.length, query]);

  useEffect(() => {
    if (!enableShortcut) {
      return;
    }
    if (typeof window === "undefined") {
      return;
    }
    const handleKeydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === shortcutKey.toLowerCase()) {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [enableShortcut, shortcutKey]);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed && !onSubmit) {
      return;
    }
    onSubmit?.(trimmed);
  };

  const handleSearchChange = (next: string) => {
    if (!isControlled) {
      setUncontrolledQuery(next);
    }
    onChange?.(next);
  };

  const handleClear = () => {
    if (!query) {
      return;
    }
    if (!isControlled) {
      setUncontrolledQuery("");
    }
    onChange?.("");
    onClear?.();
    searchInputRef.current?.focus();
  };

  const handleSuggestionSelection = (suggestion?: GlobalSearchSuggestion) => {
    if (!suggestion) {
      return;
    }
    onSelectSuggestion?.(suggestion);
    suggestion.action?.();
    setIsFocused(false);
    searchInputRef.current?.blur();
  };

  const handleSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (!showDropdown || !hasSuggestions) {
      if (event.key === "Escape") {
        setIsFocused(false);
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
      setIsFocused(false);
      event.currentTarget.blur();
    }
  };

  const variantClasses =
    variant === "minimal"
      ? "rounded-lg border border-slate-200 bg-white shadow-sm focus-within:border-brand-200"
      : "rounded-xl border border-slate-200/70 bg-gradient-to-r from-white/95 via-slate-50/80 to-white/95 shadow-[0_20px_45px_-30px_rgba(15,23,42,0.65)] ring-1 ring-inset ring-white/80 transition focus-within:border-brand-200 focus-within:shadow-[0_25px_55px_-35px_rgba(79,70,229,0.55)] sm:rounded-2xl";

  return (
    <div className={clsx("relative", className)}>
      <div className={clsx("group/search overflow-hidden", variantClasses, showDropdown && variant === "default" && "focus-within:shadow-[0_35px_80px_-40px_rgba(79,70,229,0.55)]")}>
        <form className="flex w-full items-center gap-3 px-4 py-2 text-sm text-slate-600 sm:px-5 sm:py-2.5" role="search" aria-label={searchAriaLabel} onSubmit={handleSearchSubmit}>
          <label htmlFor={inputId} className="sr-only">
            {searchAriaLabel}
          </label>
          {leadingIcon ?? (
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-white/90 text-brand-600 shadow-inner shadow-white/60 ring-1 ring-inset ring-white/70 sm:h-10 sm:w-10 sm:rounded-xl">
              <SearchIcon className="h-4 w-4 flex-shrink-0 text-brand-600" />
            </span>
          )}
          <div className="flex min-w-0 flex-1 flex-col">
            {scopeLabel ? (
              <span className="text-[0.6rem] font-semibold uppercase tracking-wide text-slate-400 sm:text-[0.65rem]">
                {scopeLabel}
              </span>
            ) : null}
            <input
              ref={searchInputRef}
              id={inputId}
              type="search"
              value={query}
              onChange={(event) => handleSearchChange(event.target.value)}
            onFocus={() => {
              setIsFocused(true);
              onFocus?.();
              // keep highlight stable if no suggestions
              if (!hasSuggestions) {
                setHighlightedSuggestion(0);
                }
              }}
            onBlur={() => {
              setIsFocused(false);
              onBlur?.();
            }}
              onKeyDown={handleSearchKeyDown}
              placeholder={placeholder}
              className="w-full border-0 bg-transparent text-base font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none"
              aria-expanded={showDropdown}
              aria-controls={showDropdown ? suggestionsListId : undefined}
            />
          </div>
          <div className="flex items-center gap-1">
            {canClear && query ? (
              <button
                type="button"
                onClick={handleClear}
                aria-label="Clear search"
                className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-full border border-transparent text-slate-400 hover:border-slate-200 hover:bg-white"
              >
                <CloseIcon className="h-3.5 w-3.5" />
              </button>
            ) : null}
            {isLoading ? (
              <span className="inline-flex h-7 w-7 items-center justify-center" aria-live="polite" aria-label={loadingLabel}>
                <SpinnerIcon className="h-4 w-4 text-brand-600" />
              </span>
            ) : null}
            {trailingIcon}
            {shortcutLabel ? (
              <span className="hidden items-center gap-1 rounded-full border border-slate-200/80 bg-white/80 px-2 py-1 text-xs font-semibold text-slate-500 shadow-inner shadow-white/60 md:inline-flex">
                {shortcutLabel}
              </span>
            ) : null}
          </div>
        </form>
      </div>
      {showDropdown ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/95 shadow-[0_35px_80px_-40px_rgba(79,70,229,0.55)] ring-1 ring-inset ring-white/80">
          {hasSuggestions ? (
            <ul id={suggestionsListId} role="listbox" aria-label="Search suggestions" className="divide-y divide-slate-100/80">
              {suggestions.map((suggestion, index) => {
                const active = index === highlightedSuggestion;
                const content =
                  renderSuggestion?.({ suggestion, active }) ?? (
                    <DefaultSuggestion suggestion={suggestion} active={active} />
                  );
                return (
                  <li key={suggestion.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={active}
                      onMouseEnter={() => setHighlightedSuggestion(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => handleSuggestionSelection(suggestion)}
                      className={clsx("flex w-full px-5 py-3 text-left transition", active ? "bg-brand-50/60" : "hover:bg-slate-50/80")}
                    >
                      {content}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {showEmptyState ? (
            <div className="px-5 py-4 text-sm text-slate-500" role="status">
              {emptyState}
            </div>
          ) : null}
          {hasFilters ? (
            <div className="border-t border-slate-100/80 bg-slate-50/60 px-4 py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500">
                <span className="uppercase tracking-wide text-[0.6rem] text-slate-400">Filters:</span>
                {filters?.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => onSelectFilter?.(filter)}
                    className={clsx(
                      "focus-ring inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold transition",
                      filter.active ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-500 hover:border-slate-300",
                    )}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DefaultSuggestion({ suggestion, active }: { suggestion: GlobalSearchSuggestion; active: boolean }) {
  return (
    <div className="flex w-full items-start gap-3">
      {suggestion.icon ? (
        <span className="mt-0.5 text-slate-400">{suggestion.icon}</span>
      ) : (
        <span className="mt-1 h-2.5 w-2.5 rounded-full bg-slate-200" aria-hidden />
      )}
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">{suggestion.label}</span>
          {suggestion.shortcutHint ? (
            <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-slate-400">
              {suggestion.shortcutHint}
            </span>
          ) : null}
        </span>
        {suggestion.description ? (
          <span className={clsx("text-xs", active ? "text-brand-700" : "text-slate-500")}>{suggestion.description}</span>
        ) : null}
      </span>
    </div>
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

function CloseIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 6l8 8" strokeLinecap="round" />
      <path d="M14 6l-8 8" strokeLinecap="round" />
    </svg>
  );
}

function SpinnerIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={clsx("animate-spin", className)} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-70" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
