import {
  type ComponentType,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type SVGProps,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import clsx from "clsx";

import { useNavigate } from "react-router-dom";
import { getDefaultWorkspacePath } from "@/navigation/workspacePaths";
import {
  GLOBAL_SEARCH_TRIGGER_LENGTH,
  type GlobalSearchScope,
  useGlobalSearchData,
} from "@/hooks/use-global-search";
import { useShortcutHint } from "@/hooks/useShortcutHint";
import { CloseIcon, DirectoryIcon, DocumentIcon, RunsIcon, SearchIcon, SpinnerIcon } from "@/components/icons";

const DEBOUNCE_DELAY_MS = 200;
const GLOBAL_SEARCH_WORKSPACE_NAME_FILTER_ID = "global-search-workspace-name";
const GLOBAL_SEARCH_WORKSPACE_SLUG_FILTER_ID = "global-search-workspace-slug";

type GlobalNavItem = {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly icon?: ComponentType<SVGProps<SVGSVGElement>>;
};

export type GlobalNavSearchScope =
  | {
      readonly kind: "workspace";
      readonly workspaceId: string;
      readonly workspaceName: string;
      readonly navItems: readonly GlobalNavItem[];
    }
  | {
      readonly kind: "directory";
    };

type GlobalSearchItem = {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly meta?: string;
  readonly href?: string;
  readonly onSelect?: () => void;
};

type GlobalSearchSection = {
  readonly id: string;
  readonly label: string;
  readonly items: readonly GlobalSearchItem[];
};

export interface GlobalNavSearchProps {
  readonly scope: GlobalNavSearchScope;
  readonly className?: string;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly enableShortcut?: boolean;
}

export function GlobalNavSearch({
  scope,
  className,
  placeholder,
  ariaLabel,
  enableShortcut = true,
}: GlobalNavSearchProps) {
  const navigate = useNavigate();
  const shortcutHint = useShortcutHint();
  const generatedId = useId();
  const inputId = `${generatedId}-input`;
  const listId = `${generatedId}-list`;
  const statusId = `${generatedId}-status`;
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const normalizedQuery = query.trim();
  const shouldSearch = normalizedQuery.length >= GLOBAL_SEARCH_TRIGGER_LENGTH;

  useEffect(() => {
    if (!normalizedQuery) {
      setDebouncedQuery("");
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setDebouncedQuery(normalizedQuery);
    }, DEBOUNCE_DELAY_MS);

    return () => window.clearTimeout(timeoutId);
  }, [normalizedQuery]);

  const searchScope: GlobalSearchScope =
    scope.kind === "workspace"
      ? { kind: "workspace", workspaceId: scope.workspaceId }
      : { kind: "directory" };

  const { documents, runs, workspaces, isFetching, isError } = useGlobalSearchData({
    scope: searchScope,
    query: debouncedQuery,
    enabled: isOpen,
  });

  const navItems = useMemo(() => {
    if (scope.kind !== "workspace") return [];
    if (!normalizedQuery) return scope.navItems;
    const loweredQuery = normalizedQuery.toLowerCase();
    return scope.navItems.filter((item) => {
      const label = item.label.toLowerCase();
      return label.includes(loweredQuery) || item.id.toLowerCase().includes(loweredQuery);
    });
  }, [normalizedQuery, scope.kind, scope.navItems]);

  const isQueryStale = normalizedQuery !== debouncedQuery;
  const canShowRemoteResults = shouldSearch && !isQueryStale;

  const sections = useMemo(() => {
    const next: GlobalSearchSection[] = [];

    if (navItems.length > 0) {
      next.push({
        id: "navigate",
        label: "Jump to",
        items: navItems.map((item) => ({
          id: `nav-${item.id}`,
          label: item.label,
          description: "Workspace section",
          icon: item.icon ? <item.icon className="h-4 w-4 text-muted-foreground" aria-hidden /> : undefined,
          href: item.href,
          meta: "Section",
        })),
      });
    }

    if (canShowRemoteResults && scope.kind === "workspace") {
      const documentItems = documents.map((document) => {
        const label = document.name || "Untitled document";
        const phase = document.lastRun?.phase;
        const phaseLabel = phase ? `${phase[0]?.toUpperCase() ?? ""}${phase.slice(1)}` : null;
        return {
          id: `document-${document.id}`,
          label,
          description: phaseLabel ? `Last run: ${phaseLabel}` : "Document",
          icon: <DocumentIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
          href: buildDocumentsSearchHref(scope.workspaceId, normalizedQuery, document.id),
        };
      });
      const viewAllDocuments = {
        id: "documents-all",
        label: "Search documents",
        description: `View all document results for "${normalizedQuery}"`,
        icon: <DocumentIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
        href: buildDocumentsSearchHref(scope.workspaceId, normalizedQuery),
        meta: "All",
      };
      next.push({
        id: "documents",
        label: "Documents",
        items: documentItems.length > 0 ? [...documentItems, viewAllDocuments] : [viewAllDocuments],
      });

      const runItems = runs.map((run) => {
        const label = run.input?.filename ?? run.input?.document_id ?? `Run ${run.id}`;
        return {
          id: `run-${run.id}`,
          label,
          description: run.status ? `Status: ${run.status}` : "Run",
          icon: <RunsIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
          href: buildRunsSearchHref(scope.workspaceId, run.id),
        };
      });
      const viewAllRuns = {
        id: "runs-all",
        label: "Search runs",
        description: `View all run results for "${normalizedQuery}"`,
        icon: <RunsIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
        href: buildRunsSearchHref(scope.workspaceId),
        meta: "All",
      };
      next.push({
        id: "runs",
        label: "Runs",
        items: runItems.length > 0 ? [...runItems, viewAllRuns] : [viewAllRuns],
      });
    }

    if (canShowRemoteResults && scope.kind === "directory") {
      const workspaceItems = workspaces.map((workspace) => ({
        id: `workspace-${workspace.id}`,
        label: workspace.name,
        description: workspace.slug ? `Slug: ${workspace.slug}` : "Workspace",
        icon: <DirectoryIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
        href: getDefaultWorkspacePath(workspace.id),
        meta: "Workspace",
      }));

      if (workspaceItems.length > 0) {
        next.push({
          id: "workspaces",
          label: "Workspaces",
          items: workspaceItems,
        });
      }
    }

    return next;
  }, [
    canShowRemoteResults,
    documents,
    navItems,
    normalizedQuery,
    runs,
    scope.kind,
    scope.workspaceId,
    workspaces,
  ]);

  const flatItems = useMemo(
    () => sections.flatMap((section) => section.items),
    [sections],
  );
  const sectionOffsets = useMemo(() => {
    let offset = 0;
    return sections.map((section) => {
      const start = offset;
      offset += section.items.length;
      return start;
    });
  }, [sections]);

  useEffect(() => {
    if (flatItems.length === 0) {
      setActiveIndex(0);
      return;
    }
    if (activeIndex >= flatItems.length) {
      setActiveIndex(0);
    }
  }, [activeIndex, flatItems.length]);

  useEffect(() => {
    setActiveIndex(0);
  }, [normalizedQuery]);

  useEffect(() => {
    if (!isOpen) setActiveIndex(0);
  }, [isOpen]);

  useEffect(() => {
    if (!enableShortcut) return;
    if (typeof window === "undefined") return;

    const handleKeydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        const target = event.target as EventTarget | null;
        const isInsideSearch = !!(target && target instanceof Node && rootRef.current?.contains(target));
        if (!isInsideSearch && isEditableTarget(target)) return;

        event.preventDefault();
        inputRef.current?.focus({ preventScroll: true });
      }
    };

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [enableShortcut]);

  const isSearchPending = isOpen && shouldSearch && (isQueryStale || isFetching);
  const hasResults = flatItems.length > 0;
  const fallbackHref =
    shouldSearch && normalizedQuery
      ? scope.kind === "workspace"
        ? buildDocumentsSearchHref(scope.workspaceId, normalizedQuery)
        : buildWorkspacesSearchHref(normalizedQuery)
      : null;

  let statusMessage: string | null = null;
  if (isError) {
    statusMessage = hasResults
      ? "Some results may be unavailable right now."
      : "Search is unavailable right now.";
  } else if (isSearchPending && !hasResults) {
    statusMessage = "Searching...";
  } else if (!hasResults && !isSearchPending) {
    if (!normalizedQuery) {
      statusMessage = scope.kind === "workspace"
        ? "Search documents, runs, and workspace navigation."
        : "Search workspaces by name or slug.";
    } else if (!shouldSearch) {
      statusMessage = `Type at least ${GLOBAL_SEARCH_TRIGGER_LENGTH} characters to search.`;
    } else {
      statusMessage = `No matches for "${normalizedQuery}".`;
    }
  }

  const showDropdown = isOpen && (hasResults || isSearchPending || Boolean(statusMessage));

  const searchPlaceholder =
    placeholder ??
    (scope.kind === "workspace" ? `Search ${scope.workspaceName}` : "Search workspaces");

  const handleQueryChange = (next: string) => {
    setQuery(next);
    if (!isOpen) {
      setIsOpen(true);
    }
  };

  const handleClear = () => {
    if (!query) return;
    setQuery("");
    setDebouncedQuery("");
    inputRef.current?.focus({ preventScroll: true });
  };

  const close = () => {
    setIsOpen(false);
  };

  const handleSelectItem = (
    item: GlobalSearchItem | undefined,
    options: { preserveQuery?: boolean; skipNavigate?: boolean } = {},
  ) => {
    if (!item) return;
    item.onSelect?.();
    if (item.href && !options.skipNavigate) {
      navigate(item.href);
    }
    if (!options.preserveQuery) {
      setQuery("");
      setDebouncedQuery("");
      close();
      const active = document.activeElement as HTMLElement | null;
      if (active && rootRef.current?.contains(active)) {
        active.blur();
      }
    }
  };

  const handleItemClick = (event: ReactMouseEvent<HTMLElement>, item: GlobalSearchItem) => {
    const hasModifier =
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      event.button === 1;
    handleSelectItem(item, { preserveQuery: hasModifier, skipNavigate: true });
    if (event.defaultPrevented || hasModifier) return;
    if (item.href) {
      event.preventDefault();
      navigate(item.href);
    }
  };

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      if (!showDropdown || flatItems.length === 0) return;
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % flatItems.length);
      return;
    }

    if (event.key === "ArrowUp") {
      if (!showDropdown || flatItems.length === 0) return;
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + flatItems.length) % flatItems.length);
      return;
    }

    if (event.key === "Home") {
      if (!showDropdown || flatItems.length === 0) return;
      event.preventDefault();
      setActiveIndex(0);
      return;
    }

    if (event.key === "End") {
      if (!showDropdown || flatItems.length === 0) return;
      event.preventDefault();
      setActiveIndex(flatItems.length - 1);
      return;
    }

    if (event.key === "Enter") {
      if (showDropdown && flatItems.length > 0) {
        event.preventDefault();
        handleSelectItem(flatItems[activeIndex]);
        return;
      }
      if (fallbackHref) {
        event.preventDefault();
        navigate(fallbackHref);
        setQuery("");
        setDebouncedQuery("");
        close();
      }
    }
  };

  return (
    <div
      ref={rootRef}
      className={clsx("relative w-full min-w-0", className)}
      onFocusCapture={() => setIsOpen(true)}
      onBlurCapture={() => {
        requestAnimationFrame(() => {
          const root = rootRef.current;
          const active = document.activeElement;
          const stillInside = !!(root && active && root.contains(active));
          if (!stillInside) close();
        });
      }}
      onKeyDownCapture={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        if (isOpen) {
          close();
          inputRef.current?.focus({ preventScroll: true });
          return;
        }
        if (query) {
          handleClear();
        }
      }}
    >
      <div
        className={clsx(
          "flex h-[var(--app-shell-control-h)] items-center gap-3 rounded-2xl border border-border/60 bg-background/70 px-3 shadow-sm ring-1 ring-inset ring-border/30 backdrop-blur-sm transition",
          "focus-within:border-ring focus-within:bg-background focus-within:ring-ring/40",
        )}
      >
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-background/80 text-muted-foreground ring-1 ring-inset ring-border/40">
          <SearchIcon className="h-4 w-4" aria-hidden />
        </span>
        <input
          ref={inputRef}
          id={inputId}
          type="search"
          value={query}
          onChange={(event) => handleQueryChange(event.target.value)}
          onKeyDown={handleInputKeyDown}
          role="combobox"
          aria-label={ariaLabel ?? searchPlaceholder}
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-expanded={showDropdown}
          aria-controls={showDropdown && flatItems.length > 0 ? listId : undefined}
          aria-activedescendant={
            showDropdown && flatItems.length > 0 ? `${listId}-option-${activeIndex}` : undefined
          }
          aria-describedby={showDropdown && statusMessage ? statusId : undefined}
          placeholder={searchPlaceholder}
          autoComplete="off"
          className="w-full min-w-0 border-0 bg-transparent text-sm font-medium text-foreground placeholder:text-muted-foreground focus:outline-none"
        />

        <div className="flex items-center gap-1">
          {query ? (
            <button
              type="button"
              onClick={handleClear}
              className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-transparent text-muted-foreground transition hover:border-border/60 hover:bg-background/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              aria-label="Clear search"
            >
              <CloseIcon className="h-3.5 w-3.5" />
            </button>
          ) : null}

          {isSearchPending ? (
            <span className="inline-flex h-7 w-7 items-center justify-center" aria-live="polite" aria-label="Searching">
              <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" />
            </span>
          ) : null}

          {enableShortcut ? (
            <span className="hidden items-center gap-1 rounded-full border border-border/40 bg-background/80 px-2 py-1 text-xs font-semibold text-muted-foreground shadow-inner sm:inline-flex">
              {shortcutHint}
            </span>
          ) : null}
        </div>
      </div>

      {showDropdown ? (
        <div
          className="absolute left-0 right-0 top-full z-[var(--app-z-header)] mt-2 overflow-hidden rounded-2xl border border-border/70 bg-popover shadow-2xl ring-1 ring-inset ring-border/30"
        >
          {sections.length > 0 ? (
            <div
              className="divide-y divide-border/60"
              role="listbox"
              aria-label="Global search results"
              id={listId}
              aria-busy={isSearchPending}
            >
              {sections.map((section, sectionIndex) => {
                const sectionIndexOffset = sectionOffsets[sectionIndex] ?? 0;
                return (
                  <div key={section.id} className="py-2">
                    <div className="px-4 pb-2 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      {section.label}
                    </div>
                    <div className="flex flex-col">
                      {section.items.map((item, itemIndex) => {
                        const absoluteIndex = sectionIndexOffset + itemIndex;
                        const isActive = absoluteIndex === activeIndex;
                        const rowClassName = clsx(
                          "flex w-full cursor-pointer items-start gap-3 px-4 py-2.5 text-left transition",
                          isActive ? "bg-muted" : "hover:bg-muted",
                        );
                        return (
                          item.href ? (
                            <a
                              key={item.id}
                              href={item.href}
                              id={`${listId}-option-${absoluteIndex}`}
                              role="option"
                              aria-selected={isActive}
                              tabIndex={-1}
                              onMouseEnter={() => setActiveIndex(absoluteIndex)}
                              onClick={(event) => handleItemClick(event, item)}
                              className={rowClassName}
                            >
                              {item.icon ? (
                                <span className="mt-0.5 text-muted-foreground">{item.icon}</span>
                              ) : (
                                <span className="mt-2 h-2 w-2 rounded-full bg-border" aria-hidden />
                              )}
                              <span className="flex min-w-0 flex-1 flex-col">
                                <span className="flex items-center gap-2">
                                  <span className="truncate text-sm font-semibold text-foreground">{item.label}</span>
                                  {item.meta ? (
                                    <span className="rounded border border-border bg-card px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-muted-foreground">
                                      {item.meta}
                                    </span>
                                  ) : null}
                                </span>
                                {item.description ? (
                                  <span
                                    className={clsx(
                                      "text-xs",
                                      isActive ? "text-foreground" : "text-muted-foreground",
                                    )}
                                  >
                                    {item.description}
                                  </span>
                                ) : null}
                              </span>
                            </a>
                          ) : (
                            <button
                              key={item.id}
                              id={`${listId}-option-${absoluteIndex}`}
                              type="button"
                              role="option"
                              aria-selected={isActive}
                              tabIndex={-1}
                              onMouseEnter={() => setActiveIndex(absoluteIndex)}
                              onClick={() => handleSelectItem(item)}
                              className={rowClassName}
                            >
                              {item.icon ? (
                                <span className="mt-0.5 text-muted-foreground">{item.icon}</span>
                              ) : (
                                <span className="mt-2 h-2 w-2 rounded-full bg-border" aria-hidden />
                              )}
                              <span className="flex min-w-0 flex-1 flex-col">
                                <span className="flex items-center gap-2">
                                  <span className="truncate text-sm font-semibold text-foreground">{item.label}</span>
                                  {item.meta ? (
                                    <span className="rounded border border-border bg-card px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-muted-foreground">
                                      {item.meta}
                                    </span>
                                  ) : null}
                                </span>
                                {item.description ? (
                                  <span
                                    className={clsx(
                                      "text-xs",
                                      isActive ? "text-foreground" : "text-muted-foreground",
                                    )}
                                  >
                                    {item.description}
                                  </span>
                                ) : null}
                              </span>
                            </button>
                          )
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}

          {statusMessage ? (
            <div
              id={statusId}
              className="px-4 py-4 text-sm text-muted-foreground"
              role="status"
              aria-live="polite"
            >
              {statusMessage}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

type GlobalSearchFilter = {
  readonly id: string;
  readonly value: string;
  readonly variant: "text";
  readonly operator: "iLike";
  readonly filterId: string;
};

function buildTextFilter(id: string, value: string, filterId: string): GlobalSearchFilter | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return {
    id,
    value: trimmed,
    variant: "text",
    operator: "iLike",
    filterId,
  };
}

function buildFiltersParam(filters: Array<GlobalSearchFilter | null>) {
  const active = filters.filter((filter): filter is GlobalSearchFilter => Boolean(filter));
  if (!active.length) return null;
  return JSON.stringify(active);
}

function buildDocumentsSearchHref(workspaceId: string, query: string, previewDocId?: string) {
  return buildSearchHref(`/workspaces/${workspaceId}/documents`, {
    previewDocId,
    q: query,
  });
}

function buildRunsSearchHref(workspaceId: string, runId?: string) {
  return buildSearchHref(`/workspaces/${workspaceId}/runs`, {
    run: runId,
  });
}

function buildWorkspacesSearchHref(query: string) {
  const filters = buildFiltersParam([
    buildTextFilter("name", query, GLOBAL_SEARCH_WORKSPACE_NAME_FILTER_ID),
    buildTextFilter("slug", query, GLOBAL_SEARCH_WORKSPACE_SLUG_FILTER_ID),
  ]);

  return buildSearchHref("/workspaces", {
    filters,
    joinOperator: filters ? "or" : undefined,
  });
}

function buildSearchHref(path: string, params: Record<string, string | null | undefined>) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) searchParams.set(key, trimmed);
      return;
    }
    if (value) searchParams.set(key, String(value));
  });

  const search = searchParams.toString();
  return search ? `${path}?${search}` : path;
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
