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
import { CloseIcon, SearchIcon, SpinnerIcon } from "@components/icons";

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

export type GlobalSearchFieldVariant = "default" | "minimal" | "header";

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

  const rootRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const isControlled = value !== undefined;
  const [uncontrolledQuery, setUncontrolledQuery] = useState(defaultValue);

  // Focus-within (not just input focus) so keyboard users can tab into suggestions/filters.
  const [focusWithin, setFocusWithin] = useState(false);
  const focusWithinRef = useRef(false);

  const [highlightedSuggestion, setHighlightedSuggestion] = useState(0);

  const query = isControlled ? value ?? "" : uncontrolledQuery;
  const hasSuggestions = suggestions.length > 0;
  const hasFilters = Boolean(filters?.length);

  const showDropdown = focusWithin && (hasSuggestions || isLoading || Boolean(emptyState) || hasFilters);
  const showEmptyState = focusWithin && !hasSuggestions && !isLoading && Boolean(emptyState);

  const canClear = Boolean(onClear || !isControlled);
  const shortcutLabel = shortcutHint || "⌘K";
  const searchAriaLabel = ariaLabel ?? placeholder;

  const close = () => {
    if (focusWithinRef.current) {
      focusWithinRef.current = false;
      setFocusWithin(false);
      onBlur?.();
    }
  };

  useEffect(() => {
    if (!isControlled) {
      setUncontrolledQuery(defaultValue);
    }
  }, [defaultValue, isControlled]);

  useEffect(() => {
    setHighlightedSuggestion(0);
  }, [suggestions.length, query]);

  useEffect(() => {
    if (!enableShortcut) return;
    if (typeof window === "undefined") return;

    const handleKeydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === shortcutKey.toLowerCase()) {
        // Don’t hijack Cmd/Ctrl+K when the user is typing in another input/editor.
        const target = event.target as EventTarget | null;
        const isInsideThisSearch = !!(target && target instanceof Node && rootRef.current?.contains(target));
        if (!isInsideThisSearch && isEditableTarget(target)) return;

        event.preventDefault();
        searchInputRef.current?.focus({ preventScroll: true });
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
    if (!query) return;

    if (!isControlled) {
      setUncontrolledQuery("");
    }
    onChange?.("");
    onClear?.();
    searchInputRef.current?.focus({ preventScroll: true });
  };

  const handleSuggestionSelection = (suggestion?: GlobalSearchSuggestion) => {
    if (!suggestion) return;

    onSelectSuggestion?.(suggestion);
    suggestion.action?.();

    close();
    // Blur whatever is focused inside the search so the dropdown closes cleanly.
    const active = document.activeElement as HTMLElement | null;
    if (active && rootRef.current?.contains(active)) active.blur();
  };

  const handleSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      event.currentTarget.blur();
      return;
    }

    if (!showDropdown || !hasSuggestions) {
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
    }
  };

  const isHeaderVariant = variant === "header";
  const variantClasses = isHeaderVariant
    ? clsx(
        "rounded-2xl border border-border/50 bg-background/60 text-foreground backdrop-blur-sm",
        "shadow-none ring-1 ring-inset ring-border/30 transition",
        "focus-within:border-ring focus-within:bg-background/80 focus-within:ring-ring/40",
      )
      : variant === "minimal"
        ? clsx(
          "rounded-xl border border-border bg-card/90 shadow-sm ring-1 ring-inset ring-border/40",
          "transition focus-within:border-ring focus-within:shadow-lg",
        )
        : clsx(
          "rounded-xl border border-border/70 bg-gradient-to-r from-card/95 via-muted/80 to-card/95",
          "shadow-lg ring-1 ring-inset ring-border/30 transition",
          "focus-within:border-ring focus-within:shadow-xl sm:rounded-2xl",
        );

  const formTextClass = "text-muted-foreground";
  const inputTextClass = "text-foreground placeholder:text-muted-foreground";
  const shortcutClass = isHeaderVariant
    ? "border-border/40 bg-background/80 text-foreground"
    : "border-border/70 bg-card/80 text-muted-foreground";
  const shortcutVisibilityClass = isHeaderVariant ? "lg:inline-flex" : "md:inline-flex";
  const clearButtonClass = isHeaderVariant
    ? "text-muted-foreground hover:border-border/50 hover:bg-background/60"
    : "text-muted-foreground hover:border-border hover:bg-card";
  const leadingIconClass = isHeaderVariant
    ? "bg-background/60 text-muted-foreground ring-border/40"
    : "bg-card text-muted-foreground ring-border/40";

  return (
    <div
      ref={rootRef}
      className={clsx("relative", className)}
      onFocusCapture={() => {
        if (!focusWithinRef.current) {
          focusWithinRef.current = true;
          setFocusWithin(true);
          onFocus?.();
        }
      }}
      onBlurCapture={() => {
        // Close only when focus truly leaves the whole widget (input + dropdown).
        requestAnimationFrame(() => {
          const root = rootRef.current;
          const active = document.activeElement;
          const stillInside = !!(root && active && root.contains(active));
          if (!stillInside) close();
        });
      }}
      onKeyDownCapture={(event: ReactKeyboardEvent<HTMLDivElement>) => {
        if (event.key === "Escape") {
          event.preventDefault();
          close();
          const active = document.activeElement as HTMLElement | null;
          if (active && rootRef.current?.contains(active)) active.blur();
        }
      }}
    >
      <div
        className={clsx(
          "group/search overflow-hidden",
          variantClasses,
          showDropdown &&
            variant === "default" &&
            "focus-within:shadow-2xl",
        )}
      >
        <form
          className={clsx("flex w-full items-center gap-3 px-4 py-2 text-sm sm:px-5 sm:py-2.5", formTextClass)}
          role="search"
          aria-label={searchAriaLabel}
          onSubmit={handleSearchSubmit}
        >
          <label htmlFor={inputId} className="sr-only">
            {searchAriaLabel}
          </label>

          {leadingIcon ?? (
            <span
              className={clsx(
                "inline-flex h-9 w-9 items-center justify-center rounded-xl shadow-inner ring-1 ring-inset sm:h-10 sm:w-10",
                leadingIconClass,
              )}
            >
              <SearchIcon className="h-4 w-4 flex-shrink-0" />
            </span>
          )}

          <div className="flex min-w-0 flex-1 flex-col">
            {scopeLabel ? (
              <span
                className={clsx(
                  "text-[0.6rem] font-semibold uppercase tracking-wide sm:text-[0.65rem]",
                  "text-muted-foreground",
                )}
              >
                {scopeLabel}
              </span>
            ) : null}

            <input
              ref={searchInputRef}
              id={inputId}
              type="search"
              value={query}
              onChange={(event) => handleSearchChange(event.target.value)}
              role="combobox"
              aria-autocomplete="list"
              aria-haspopup="listbox"
              onKeyDown={handleSearchKeyDown}
              placeholder={placeholder}
              className={clsx("w-full border-0 bg-transparent text-base font-medium focus:outline-none", inputTextClass)}
              aria-expanded={showDropdown}
              aria-controls={showDropdown ? suggestionsListId : undefined}
              aria-activedescendant={
                showDropdown && hasSuggestions ? `${suggestionsListId}-option-${highlightedSuggestion}` : undefined
              }
            />
          </div>

          <div className="flex items-center gap-1">
            {canClear && query ? (
              <button
                type="button"
                onClick={handleClear}
                aria-label="Clear search"
                className={clsx(
                  "inline-flex h-7 w-7 items-center justify-center rounded-full border border-transparent transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  clearButtonClass,
                )}
              >
                <CloseIcon className="h-3.5 w-3.5" />
              </button>
            ) : null}

            {isLoading ? (
              <span
                className="inline-flex h-7 w-7 items-center justify-center"
                aria-live="polite"
                aria-label={loadingLabel}
              >
                <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" />
              </span>
            ) : null}

            {trailingIcon}

            {shortcutLabel ? (
              <span
                className={clsx(
                  "hidden items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold shadow-inner",
                  shortcutClass,
                  shortcutVisibilityClass,
                )}
              >
                {shortcutLabel}
              </span>
            ) : null}
          </div>
        </form>
      </div>

      {showDropdown ? (
        <div className="absolute left-0 right-0 top-full z-[var(--app-z-header)] mt-2 overflow-hidden rounded-2xl border border-border/70 bg-popover shadow-2xl ring-1 ring-inset ring-border/30">
          {hasSuggestions ? (
            <ul id={suggestionsListId} role="listbox" aria-label="Search suggestions" className="divide-y divide-border/60">
              {suggestions.map((suggestion, index) => {
                const active = index === highlightedSuggestion;
                const content =
                  renderSuggestion?.({ suggestion, active }) ?? (
                    <DefaultSuggestion suggestion={suggestion} active={active} />
                  );

                return (
                  <li key={suggestion.id}>
                    <button
                      id={`${suggestionsListId}-option-${index}`}
                      type="button"
                      role="option"
                      aria-selected={active}
                      onMouseEnter={() => setHighlightedSuggestion(index)}
                      onClick={() => handleSuggestionSelection(suggestion)}
                      className={clsx(
                        "flex w-full px-5 py-3 text-left transition",
                        active ? "bg-muted" : "hover:bg-muted",
                      )}
                    >
                      {content}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}

          {showEmptyState ? (
            <div className="px-5 py-4 text-sm text-muted-foreground" role="status">
              {emptyState}
            </div>
          ) : null}

          {hasFilters ? (
            <div className="border-t border-border/60 bg-muted/60 px-4 py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-muted-foreground">
                <span className="uppercase tracking-wide text-[0.6rem] text-muted-foreground">Filters:</span>
                {filters?.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    onClick={() => onSelectFilter?.(filter)}
                    className={clsx(
                      "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      filter.active
                        ? "border-ring bg-muted text-foreground"
                        : "border-border bg-card text-muted-foreground hover:border-ring/40",
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
        <span className="mt-0.5 text-muted-foreground">{suggestion.icon}</span>
      ) : (
        <span className="mt-1 h-2.5 w-2.5 rounded-full bg-border" aria-hidden />
      )}
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{suggestion.label}</span>
          {suggestion.shortcutHint ? (
            <span className="rounded border border-border bg-card px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-muted-foreground">
              {suggestion.shortcutHint}
            </span>
          ) : null}
        </span>
        {suggestion.description ? (
          <span className={clsx("text-xs", active ? "text-foreground" : "text-muted-foreground")}>{suggestion.description}</span>
        ) : null}
      </span>
    </div>
  );
}

function isEditableTarget(target: EventTarget | null) {
  if (!target) return false;
  if (!(target instanceof HTMLElement)) return false;

  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (target.isContentEditable) return true;
  if (target.closest?.("[contenteditable='true']")) return true;

  return false;
}
