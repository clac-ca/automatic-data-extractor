import { useEffect, useState, type ReactNode } from "react";
import { FileText } from "lucide-react";
import { createSearchParams, useNavigate } from "react-router-dom";

import { fetchWorkspaceDocuments, type DocumentListRow } from "@/api/documents";
import { cn } from "@/lib/utils";
import {
  Search,
  SearchGroup,
  SearchInput,
  SearchItem,
  SearchList,
  SearchSeparator,
} from "@/components/ui/search";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useDocumentSearchRecents } from "@/pages/Workspace/hooks/useDocumentSearchRecents";

const SEARCH_DEBOUNCE_MS = 200;
const SEARCH_MIN_LENGTH = 2;
const SEARCH_RESULT_LIMIT = 10;

type SearchState = {
  status: "idle" | "loading" | "success" | "error";
  items: DocumentListRow[];
};

export function WorkspaceDocumentsTopbarSearch({ className }: { readonly className?: string }) {
  const navigate = useNavigate();
  const { workspace } = useWorkspaceContext();
  const { recents, pushRecent, clearRecents } = useDocumentSearchRecents(workspace.id);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [state, setState] = useState<SearchState>({ status: "idle", items: [] });

  const results = state.items;
  const documentsLink = `/workspaces/${workspace.id}/documents`;
  const normalizedQuery = query.trim();
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

  useEffect(() => {
    setOpen(false);
    setQuery("");
    setDebouncedQuery("");
    setState({ status: "idle", items: [] });
  }, [workspace.id]);

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
        joinOperator: null,
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

  const handleSelect = (documentId: string, label: string) => {
    pushRecent({ id: documentId, label });
    const params = createSearchParams({
      docId: documentId,
      panes: "preview",
      ...(normalizedQuery ? { q: normalizedQuery } : {}),
    });
    navigate(`${documentsLink}?${params.toString()}`);
    setQuery("");
    setOpen(false);
  };

  const handleViewAllDocuments = () => {
    navigate(documentsLink);
    setQuery("");
    setOpen(false);
  };

  const handleViewAll = () => {
    const params = createSearchParams({ q: normalizedQuery });
    navigate(`${documentsLink}?${params.toString()}`);
    setQuery("");
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Search
        shouldFilter={false}
        label="Search documents"
        className={cn(
          "w-full overflow-hidden rounded-full border border-border/60 bg-background/80 text-foreground shadow-sm backdrop-blur-sm",
          "focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30",
          "[&_[cmdk-input-wrapper]]:border-b-0",
          className,
        )}
      >
        <PopoverAnchor asChild>
          <div className="w-full">
            <SearchInput
              value={query}
              onValueChange={(value) => {
                setQuery(value);
                setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              placeholder="Search documents..."
              className="!h-9 !py-0"
            />
          </div>
        </PopoverAnchor>

        <PopoverContent
          data-slot="documents-search-popover-content"
          align="start"
          sideOffset={8}
          className="w-[var(--radix-popover-trigger-width)] max-w-[min(40rem,var(--radix-popover-content-available-width))] p-0"
        >
          <SearchList className="max-h-[min(60vh,24rem)] p-2">
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
              <SearchMessage>
                Type at least {SEARCH_MIN_LENGTH} characters to search.
              </SearchMessage>
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
        </PopoverContent>
      </Search>
    </Popover>
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
