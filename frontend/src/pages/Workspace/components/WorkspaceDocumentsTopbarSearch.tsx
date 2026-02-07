import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { FileText, Search as SearchIcon } from "lucide-react";
import { createSearchParams, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { fetchWorkspaceDocuments, type DocumentListRow } from "@/api/documents";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Search,
  SearchDialog,
  SearchGroup,
  SearchInput,
  SearchItem,
  SearchList,
  SearchSeparator,
} from "@/components/ui/search";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useDocumentSearchRecents } from "@/pages/Workspace/hooks/useDocumentSearchRecents";
import { buildDocumentDetailUrl } from "@/pages/Workspace/sections/Documents/shared/navigation";

const SEARCH_DEBOUNCE_MS = 200;
const SEARCH_MIN_LENGTH = 2;
const SEARCH_RESULT_LIMIT = 10;

type SearchState = {
  status: "idle" | "loading" | "success" | "error";
  items: DocumentListRow[];
};

export function WorkspaceDocumentsTopbarSearch({ className }: { readonly className?: string }) {
  const controller = useWorkspaceDocumentsSearchController();
  const {
    open,
    setOpen,
    query,
    setQuery,
    normalizedQuery,
    inputRef,
    activeValue,
    handleActiveValueChange,
    handleRootKeyDownCapture,
    handleRootKeyDown,
  } = controller;
  const [shortcutHint, setShortcutHint] = useState("Ctrl K");
  const anchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const ua = typeof navigator === "undefined" ? "" : navigator.userAgent;
    const isApple = /Mac|iPhone|iPad|iPod/i.test(ua);
    setShortcutHint(isApple ? "⌘ K" : "Ctrl K");
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      if (key !== "k") return;
      if (!event.metaKey && !event.ctrlKey) return;
      if (event.shiftKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      const isTypingContext =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (isTypingContext) return;

      event.preventDefault();
      setOpen(true);
      window.requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [inputRef, setOpen]);

  useEffect(() => {
    if (!open) return;
    const raf = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
    return () => window.cancelAnimationFrame(raf);
  }, [open, inputRef]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Search
        shouldFilter={false}
        label="Search documents"
        value={activeValue}
        onValueChange={handleActiveValueChange}
        onKeyDown={handleRootKeyDown}
        onKeyDownCapture={handleRootKeyDownCapture}
        className={cn(
          "w-full min-w-0 overflow-hidden rounded-full border bg-card text-card-foreground shadow-sm transition-colors",
          "border-border/70 hover:bg-card/95 dark:hover:bg-card/90",
          "focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30",
          "[&_[cmdk-input-wrapper]]:border-b-0 [&_[cmdk-input-wrapper]]:h-9 [&_[cmdk-input-wrapper]]:px-3",
          "[&_[cmdk-input]]:h-9 [&_[cmdk-input]]:py-0 [&_[cmdk-input]]:text-card-foreground",
          "[&_[data-slot=search-input-wrapper]_svg]:opacity-60",
          "cursor-text",
          className,
        )}
      >
        <PopoverAnchor asChild>
          <div ref={anchorRef} className="relative w-full">
            <SearchInput
              ref={inputRef}
              value={query}
              onValueChange={(value) => {
                setQuery(value);
                setOpen(true);
                if (controller.hasActiveFilter && value.trim().length === 0) {
                  controller.clearFilterQuery();
                }
              }}
              onFocus={() => setOpen(true)}
              placeholder="Jump to a document..."
              aria-label="Search documents"
              className="pr-16"
              onKeyDown={(event) => {
                if (event.key !== "Escape") return;
                event.preventDefault();
                if (normalizedQuery.length > 0) {
                  controller.reset();
                  return;
                }
                setOpen(false);
              }}
            />
            {normalizedQuery.length === 0 ? (
              <kbd className="pointer-events-none absolute right-3 inset-y-0 my-auto hidden h-5 items-center rounded bg-muted px-1.5 text-[10px] font-semibold leading-none text-muted-foreground lg:inline-flex">
                {shortcutHint}
              </kbd>
            ) : null}
          </div>
        </PopoverAnchor>

        <PopoverContent
          data-slot="documents-search-popover-content"
          align="start"
          sideOffset={8}
          className="w-[var(--radix-popover-trigger-width)] max-w-[min(40rem,var(--radix-popover-content-available-width))] p-0"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            inputRef.current?.focus();
            inputRef.current?.select();
          }}
          onInteractOutside={(event) => {
            const target = event.target as HTMLElement | null;
            if (target && anchorRef.current?.contains(target)) {
              event.preventDefault();
            }
          }}
        >
          <DocumentsSearchResults controller={controller} className="max-h-[min(60vh,24rem)] p-2" />
        </PopoverContent>
      </Search>
    </Popover>
  );
}

export function WorkspaceDocumentsTopbarSearchButton({
  className,
}: {
  readonly className?: string;
}) {
  const controller = useWorkspaceDocumentsSearchController({ resetOnClose: true });

  useEffect(() => {
    if (!controller.open) return;
    const raf = window.requestAnimationFrame(() => controller.inputRef.current?.focus());
    return () => window.cancelAnimationFrame(raf);
  }, [controller.open, controller.inputRef]);

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Search documents"
        className={cn("h-9 w-9", className)}
        onClick={() => controller.setOpen(true)}
      >
        <SearchIcon className="h-4 w-4" aria-hidden />
      </Button>

      <SearchDialog
        open={controller.open}
        onOpenChange={controller.setOpen}
        contentClassName="sm:max-w-2xl md:max-w-3xl"
        searchProps={{
          shouldFilter: false,
          value: controller.activeValue,
          onValueChange: controller.handleActiveValueChange,
          onKeyDown: controller.handleRootKeyDown,
          onKeyDownCapture: controller.handleRootKeyDownCapture,
        }}
      >
        <SearchInput
          ref={controller.inputRef}
          value={controller.query}
          onValueChange={controller.setQuery}
          placeholder="Jump to a document..."
          aria-label="Search documents"
        />
        <DocumentsSearchResults controller={controller} className="max-h-[60vh] p-2" />
      </SearchDialog>
    </>
  );
}

function useWorkspaceDocumentsSearchController({
  resetOnClose = false,
}: {
  readonly resetOnClose?: boolean;
} = {}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { workspace } = useWorkspaceContext();
  const { recents, pushRecent, clearRecents } = useDocumentSearchRecents(workspace.id);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [state, setState] = useState<SearchState>({ status: "idle", items: [] });
  const [activeValue, setActiveValue] = useState("");
  const hasInteractedRef = useRef(false);

  const results = state.items;
  const documentsLink = `/workspaces/${workspace.id}/documents`;
  const isDocumentsRoute = location.pathname.includes("/documents");
  const activeFilterQuery = useMemo(() => {
    if (!isDocumentsRoute) return "";
    return searchParams.get("q")?.trim() ?? "";
  }, [isDocumentsRoute, searchParams]);
  const hasActiveFilter = activeFilterQuery.length > 0;
  const normalizedQuery = useMemo(() => query.trim(), [query]);

  const showIdle = normalizedQuery.length === 0;
  const showTooShort =
    normalizedQuery.length > 0 && normalizedQuery.length < SEARCH_MIN_LENGTH;
  const showEmpty =
    !showIdle &&
    !showTooShort &&
    state.status !== "loading" &&
    state.status !== "error" &&
    state.items.length === 0;
  const showActions = normalizedQuery.length >= SEARCH_MIN_LENGTH;
  const showRefreshStatus = results.length > 0 && state.status !== "success";

  const resetSelection = useCallback(() => {
    setActiveValue("");
    hasInteractedRef.current = false;
  }, []);

  const reset = useCallback(() => {
    setQuery("");
    setDebouncedQuery("");
    setState({ status: "idle", items: [] });
    resetSelection();
  }, [resetSelection]);

  useEffect(() => {
    setOpen(false);
    reset();
  }, [reset, workspace.id]);

  useEffect(() => {
    if (!resetOnClose) return;
    if (open) return;
    reset();
  }, [open, reset, resetOnClose]);

  useEffect(() => {
    if (!open) return;
    resetSelection();
  }, [open, query, resetSelection]);

  useEffect(() => {
    if (open) return;
    if (activeFilterQuery === normalizedQuery) return;
    setQuery(activeFilterQuery);
  }, [activeFilterQuery, normalizedQuery, open]);

  useEffect(() => {
    if (!open) return;
    const handle = window.setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [open, query]);

  useEffect(() => {
    if (!open) return;
    const nextQuery = debouncedQuery.trim();
    if (nextQuery.length < SEARCH_MIN_LENGTH) {
      setState({ status: "idle", items: [] });
      return;
    }

    const controller = new AbortController();
    setState((prev) => ({ status: "loading", items: prev.items }));

    fetchWorkspaceDocuments(
      workspace.id,
      {
        limit: SEARCH_RESULT_LIMIT,
        sort: null,
        q: nextQuery,
        filters: null,
        joinOperator: undefined,
        includeTotal: false,
      },
      controller.signal,
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        setState({ status: "success", items: data.items ?? [] });
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setState((prev) => ({ status: "error", items: prev.items }));
      });

    return () => controller.abort();
  }, [debouncedQuery, open, workspace.id]);

  const handleSelect = useCallback(
    (documentId: string, label: string) => {
      pushRecent({ id: documentId, label });
      navigate(buildDocumentDetailUrl(workspace.id, documentId, { tab: "activity" }));
      reset();
      setOpen(false);
    },
    [navigate, pushRecent, reset, workspace.id],
  );

  const handleViewAllDocuments = useCallback(() => {
    navigate(documentsLink);
    reset();
    setOpen(false);
  }, [documentsLink, navigate, reset]);

  const handleViewAll = useCallback(() => {
    const params = createSearchParams({ q: normalizedQuery });
    navigate(`${documentsLink}?${params.toString()}`);
    reset();
    setOpen(false);
  }, [documentsLink, navigate, normalizedQuery, reset]);

  const clearFilterQuery = useCallback(() => {
    if (!hasActiveFilter) return;
    const next = new URLSearchParams(searchParams);
    next.delete("q");
    setSearchParams(next, { replace: true });
  }, [hasActiveFilter, searchParams, setSearchParams]);

  const handleActiveValueChange = useCallback((nextValue: string) => {
    if (!hasInteractedRef.current) return;
    setActiveValue(nextValue);
  }, []);

  const markInteraction = useCallback(() => {
    hasInteractedRef.current = true;
  }, []);

  const handleRootKeyDownCapture = useCallback((event: ReactKeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      hasInteractedRef.current = true;
    }
  }, []);

  const handleRootKeyDown = useCallback(
    (event: ReactKeyboardEvent) => {
      if (event.key !== "Enter") return;
      if (activeValue !== "") return;

      if (normalizedQuery.length === 0) {
        event.preventDefault();
        handleViewAllDocuments();
        return;
      }
      if (normalizedQuery.length >= SEARCH_MIN_LENGTH) {
        event.preventDefault();
        handleViewAll();
      }
    },
    [activeValue, handleViewAll, handleViewAllDocuments, normalizedQuery],
  );

  return {
    open,
    setOpen,
    query,
    setQuery,
    inputRef,
    state,
    results,
    normalizedQuery,
    recents,
    showIdle,
    showTooShort,
    showEmpty,
    showActions,
    showRefreshStatus,
    clearRecents,
    reset,
    handleSelect,
    handleViewAllDocuments,
    handleViewAll,
    activeValue,
    handleActiveValueChange,
    handleRootKeyDownCapture,
    handleRootKeyDown,
    markInteraction,
    activeFilterQuery,
    hasActiveFilter,
    clearFilterQuery,
  };
}

function DocumentsSearchResults({
  controller,
  className,
}: {
  readonly controller: ReturnType<typeof useWorkspaceDocumentsSearchController>;
  readonly className?: string;
}) {
  const {
    state,
    results,
    recents,
    showIdle,
    showTooShort,
    showEmpty,
    normalizedQuery,
    showActions,
    showRefreshStatus,
    handleSelect,
    handleViewAllDocuments,
    handleViewAll,
    clearRecents,
  } = controller;

  return (
    <SearchList
      className={className}
      onPointerMoveCapture={controller.markInteraction}
      onPointerDownCapture={controller.markInteraction}
    >
      {showIdle ? (
        <>
          {recents.length > 0 ? (
            <SearchGroup heading="Recent documents">
              {recents.map((recent) => (
                <SearchItem
                  key={recent.id}
                  value={recent.id}
                  onSelect={() => handleSelect(recent.id, recent.label)}
                >
                  <FileText className="text-muted-foreground" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{recent.label}</span>
                </SearchItem>
              ))}
              <SearchItem value="action:clear-recents" onSelect={clearRecents}>
                Clear recent documents
              </SearchItem>
            </SearchGroup>
          ) : (
            <SearchMessage>No recent documents yet.</SearchMessage>
          )}
          <SearchSeparator />
          <SearchGroup heading="Suggestions">
            <SearchItem value="action:view-all-documents" onSelect={handleViewAllDocuments}>
              View all documents
            </SearchItem>
          </SearchGroup>
        </>
      ) : showTooShort ? (
        <SearchMessage>Type at least {SEARCH_MIN_LENGTH} characters to search.</SearchMessage>
      ) : (
        <>
          {state.status === "loading" && results.length === 0 ? (
            <SearchMessage>Searching...</SearchMessage>
          ) : null}

          {state.status === "error" && results.length === 0 ? (
            <SearchMessage tone="error">Search is unavailable right now.</SearchMessage>
          ) : null}

          {showEmpty ? (
            <SearchMessage>No results for "{normalizedQuery}".</SearchMessage>
          ) : null}

          {results.length > 0 ? (
            <>
              <SearchGroup heading="Documents">
                {results.map((document) => (
                  <SearchItem
                    key={document.id}
                    value={document.id}
                    onSelect={() => handleSelect(document.id, document.name)}
                  >
                    <FileText className="text-muted-foreground" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate">{document.name}</span>
                  </SearchItem>
                ))}
              </SearchGroup>
              {showRefreshStatus ? (
                <>
                  <SearchSeparator />
                  <SearchMessage tone={state.status === "error" ? "error" : "muted"}>
                    {state.status === "error"
                      ? "Couldn't refresh results."
                      : "Refreshing results..."}
                  </SearchMessage>
                </>
              ) : null}
            </>
          ) : null}

          {showActions ? (
            <>
              {results.length > 0 || showRefreshStatus ? <SearchSeparator /> : null}
              <SearchGroup heading="Actions">
                <SearchItem value={`action:view-all:${normalizedQuery}`} onSelect={handleViewAll}>
                  View all results
                </SearchItem>
              </SearchGroup>
            </>
          ) : null}
        </>
      )}
    </SearchList>
  );
}

function SearchMessage({
  children,
  tone = "muted",
}: {
  readonly children: ReactNode;
  readonly tone?: "muted" | "error";
}) {
  return (
    <div
      className={
        tone === "error"
          ? "px-3 py-5 text-sm text-destructive"
          : "px-3 py-5 text-sm text-muted-foreground"
      }
    >
      {children}
    </div>
  );
}
