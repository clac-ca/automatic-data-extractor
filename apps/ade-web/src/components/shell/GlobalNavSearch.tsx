import {
  type ComponentType,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type SVGProps,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";

import { useNavigate } from "@app/navigation/history";
import { getDefaultWorkspacePath } from "@app/navigation/workspacePaths";
import { fetchWorkspaces } from "@api/workspaces/api";
import { fetchWorkspaceDocuments, type DocumentListRow } from "@api/documents";
import { fetchWorkspaceRuns, type RunResource } from "@api/runs/api";
import { useDebouncedCallback } from "@hooks/use-debounced-callback";
import { useShortcutHint } from "@hooks/useShortcutHint";
import { CloseIcon, DirectoryIcon, DocumentIcon, RunsIcon, SearchIcon, SpinnerIcon } from "@components/icons";

const SEARCH_TRIGGER_LENGTH = 2;
const RESULT_LIMIT = 5;
const DEFAULT_DOCUMENT_SORT = "-createdAt";
const DEFAULT_RUN_SORT = "-createdAt";

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
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [focusWithin, setFocusWithin] = useState(false);
  const focusWithinRef = useRef(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const updateDebouncedQuery = useDebouncedCallback((next: string) => {
    setDebouncedQuery(next.trim());
  }, 200);

  const normalizedQuery = query.trim();
  const {
    sections,
    isLoading,
    emptyMessage,
  } = useGlobalSearchResults(scope, debouncedQuery, focusWithin);
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

  const showDropdown =
    focusWithin &&
    (flatItems.length > 0 || isLoading || Boolean(emptyMessage));

  const searchPlaceholder =
    placeholder ??
    (scope.kind === "workspace" ? `Search ${scope.workspaceName}` : "Search workspaces");

  const handleQueryChange = (next: string) => {
    setQuery(next);
    updateDebouncedQuery(next);
  };

  const handleClear = () => {
    if (!query) return;
    setQuery("");
    setDebouncedQuery("");
    updateDebouncedQuery("");
    inputRef.current?.focus({ preventScroll: true });
  };

  const close = () => {
    if (!focusWithinRef.current) return;
    focusWithinRef.current = false;
    setFocusWithin(false);
  };

  const handleSelectItem = (item: GlobalSearchItem | undefined) => {
    if (!item) return;
    item.onSelect?.();
    if (item.href) {
      navigate(item.href);
    }
    setQuery("");
    setDebouncedQuery("");
    updateDebouncedQuery("");
    close();
    const active = document.activeElement as HTMLElement | null;
    if (active && rootRef.current?.contains(active)) {
      active.blur();
    }
  };

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      event.currentTarget.blur();
      return;
    }

    if (!showDropdown || flatItems.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % flatItems.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + flatItems.length) % flatItems.length);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      handleSelectItem(flatItems[activeIndex]);
    }
  };

  return (
    <div
      ref={rootRef}
      className={clsx("relative w-full min-w-0", className)}
      onFocusCapture={() => {
        if (!focusWithinRef.current) {
          focusWithinRef.current = true;
          setFocusWithin(true);
        }
      }}
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
        close();
        const active = document.activeElement as HTMLElement | null;
        if (active && rootRef.current?.contains(active)) active.blur();
      }}
    >
      <div
        className={clsx(
          "flex h-[var(--app-shell-control-h)] items-center gap-3 rounded-2xl border border-border/60 bg-background/70 px-3 shadow-sm ring-1 ring-inset ring-border/30 backdrop-blur-sm transition",
          "focus-within:border-ring focus-within:bg-background focus-within:ring-ring/40",
        )}
      >
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-background/80 text-muted-foreground ring-1 ring-inset ring-border/40">
          <SearchIcon className="h-4 w-4" />
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
          aria-controls={showDropdown ? listId : undefined}
          aria-activedescendant={
            showDropdown && flatItems.length > 0 ? `${listId}-option-${activeIndex}` : undefined
          }
          placeholder={searchPlaceholder}
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

          {isLoading ? (
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
          role="listbox"
          aria-label="Global search results"
          id={listId}
        >
          {sections.length > 0 ? (
            <div className="divide-y divide-border/60">
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
                        return (
                          <button
                            key={item.id}
                            id={`${listId}-option-${absoluteIndex}`}
                            type="button"
                            role="option"
                            aria-selected={isActive}
                            onMouseEnter={() => setActiveIndex(absoluteIndex)}
                            onClick={() => handleSelectItem(item)}
                            className={clsx(
                              "flex w-full items-start gap-3 px-4 py-2.5 text-left transition",
                              isActive ? "bg-muted" : "hover:bg-muted",
                            )}
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
                                <span className={clsx("text-xs", isActive ? "text-foreground" : "text-muted-foreground")}>
                                  {item.description}
                                </span>
                              ) : null}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}

          {sections.length === 0 && emptyMessage ? (
            <div className="px-4 py-4 text-sm text-muted-foreground" role="status">
              {emptyMessage}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function useGlobalSearchResults(scope: GlobalNavSearchScope, query: string, enabled: boolean) {
  const normalizedQuery = query.trim();
  const hasQuery = normalizedQuery.length > 0;
  const shouldSearch = normalizedQuery.length >= SEARCH_TRIGGER_LENGTH;
  const loweredQuery = normalizedQuery.toLowerCase();
  const workspaceId = scope.kind === "workspace" ? scope.workspaceId : "";

  const navItems = useMemo(() => {
    if (scope.kind !== "workspace") return [];
    if (!hasQuery) return scope.navItems;
    return scope.navItems.filter((item) => {
      const label = item.label.toLowerCase();
      return label.includes(loweredQuery) || item.id.toLowerCase().includes(loweredQuery);
    });
  }, [hasQuery, loweredQuery, scope]);

  const documentsQuery = useQuery({
    queryKey: ["global-search", "documents", workspaceId, normalizedQuery],
    queryFn: ({ signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          sort: DEFAULT_DOCUMENT_SORT,
          page: 1,
          perPage: RESULT_LIMIT,
          q: normalizedQuery,
        },
        signal,
      ),
    enabled: enabled && scope.kind === "workspace" && shouldSearch,
    staleTime: 20_000,
  });

  const runsQuery = useQuery({
    queryKey: ["global-search", "runs", workspaceId, normalizedQuery],
    queryFn: ({ signal }) =>
      fetchWorkspaceRuns(
        workspaceId,
        {
          page: 1,
          perPage: RESULT_LIMIT,
          sort: DEFAULT_RUN_SORT,
          q: normalizedQuery,
        },
        signal,
      ),
    enabled: enabled && scope.kind === "workspace" && shouldSearch,
    staleTime: 20_000,
  });

  const workspacesQuery = useQuery({
    queryKey: ["global-search", "workspaces", normalizedQuery],
    queryFn: ({ signal }) => fetchWorkspaces({ page: 1, pageSize: RESULT_LIMIT, q: normalizedQuery, signal }),
    enabled: enabled && scope.kind === "directory" && shouldSearch,
    staleTime: 30_000,
  });

  const sections: GlobalSearchSection[] = [];

  if (navItems.length > 0) {
    sections.push({
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

  if (scope.kind === "workspace" && shouldSearch) {
    const documents = (documentsQuery.data?.items ?? []) as DocumentListRow[];
    const documentItems = documents.map((document) => ({
      id: `document-${document.id}`,
      label: document.name || "Untitled document",
      description: document.status ? `Status: ${document.status}` : "Document",
      icon: <DocumentIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
      href: buildSearchHref(`/workspaces/${scope.workspaceId}/documents`, document.name || normalizedQuery),
    }));
    const viewAllDocuments = {
      id: "documents-all",
      label: "View all document results",
      description: `Search documents for "${normalizedQuery}"`,
      icon: <DocumentIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
      href: buildSearchHref(`/workspaces/${scope.workspaceId}/documents`, normalizedQuery),
      meta: "All",
    };
    const documentsSectionItems =
      documentItems.length > 0 ? [...documentItems, viewAllDocuments] : [viewAllDocuments];
    sections.push({
      id: "documents",
      label: "Documents",
      items: documentsSectionItems,
    });

    const runs = (runsQuery.data?.items ?? []) as RunResource[];
    const runItems = runs.map((run) => ({
      id: `run-${run.id}`,
      label: run.input?.filename ?? run.input?.document_id ?? `Run ${run.id}`,
      description: run.status ? `Status: ${run.status}` : "Run",
      icon: <RunsIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
      href: buildSearchHref(`/workspaces/${scope.workspaceId}/runs`, run.input?.filename ?? normalizedQuery),
    }));
    const viewAllRuns = {
      id: "runs-all",
      label: "View all run results",
      description: `Search runs for "${normalizedQuery}"`,
      icon: <RunsIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
      href: buildSearchHref(`/workspaces/${scope.workspaceId}/runs`, normalizedQuery),
      meta: "All",
    };
    const runsSectionItems = runItems.length > 0 ? [...runItems, viewAllRuns] : [viewAllRuns];
    sections.push({
      id: "runs",
      label: "Runs",
      items: runsSectionItems,
    });
  }

  if (scope.kind === "directory" && shouldSearch) {
    const workspaces = workspacesQuery.data?.items ?? [];
    const workspaceItems = workspaces.map((workspace) => ({
      id: `workspace-${workspace.id}`,
      label: workspace.name,
      description: workspace.slug ? `Slug: ${workspace.slug}` : "Workspace",
      icon: <DirectoryIcon className="h-4 w-4 text-muted-foreground" aria-hidden />,
      href: getDefaultWorkspacePath(workspace.id),
      meta: "Workspace",
    }));

    if (workspaceItems.length > 0) {
      sections.push({
        id: "workspaces",
        label: "Workspaces",
        items: workspaceItems,
      });
    }
  }

  const isLoading = documentsQuery.isFetching || runsQuery.isFetching || workspacesQuery.isFetching;
  const hasResults = sections.some((section) => section.items.length > 0);
  let emptyMessage: string | null = null;

  if (!hasResults && !isLoading) {
    if (!hasQuery) {
      emptyMessage = scope.kind === "workspace"
        ? "Start typing to search documents, runs, and workspace navigation."
        : "Search workspaces by name or slug.";
    } else if (!shouldSearch) {
      emptyMessage = "Type at least 2 characters to search.";
    } else {
      emptyMessage = `No matches for "${normalizedQuery}".`;
    }
  }

  return { sections, isLoading, emptyMessage };
}

function buildSearchHref(path: string, query: string) {
  const params = new URLSearchParams();
  const trimmed = query.trim();
  if (trimmed) params.set("q", trimmed);
  const search = params.toString();
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
