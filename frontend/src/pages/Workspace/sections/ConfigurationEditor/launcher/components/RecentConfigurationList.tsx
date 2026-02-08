import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { formatDistanceToNow } from "date-fns";
import { CopyPlus, MoreHorizontal, SearchIcon, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "../../components/StatusPill";
import { normalizeConfigStatus } from "../../utils/configs";

export interface LauncherConfigurationItem {
  readonly id: string;
  readonly displayName: string;
  readonly status: string;
  readonly updatedAt?: string | null;
  readonly isActive: boolean;
}

interface RecentConfigurationListProps {
  readonly items: readonly LauncherConfigurationItem[];
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly errorMessage?: string | null;
  readonly onRetry: () => void;
  readonly onOpenConfiguration: (configurationId: string) => void;
  readonly onSaveAsNewDraft: (configurationId: string) => void;
  readonly onArchiveDraft: (configurationId: string) => void;
  readonly isArchivingDraft: boolean;
}

export function RecentConfigurationList({
  items,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  onOpenConfiguration,
  onSaveAsNewDraft,
  onArchiveDraft,
  isArchivingDraft,
}: RecentConfigurationListProps) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const rowButtonRefs = useRef(new Map<string, HTMLButtonElement | null>());

  const filteredItems = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) {
      return items;
    }
    return items.filter((item) => item.displayName.toLowerCase().includes(term));
  }, [items, query]);

  useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredItems.some((item) => item.id === selectedId)) {
      setSelectedId(filteredItems[0]?.id ?? null);
    }
  }, [filteredItems, selectedId]);

  const handleKeyboardNavigation = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "/") {
      const activeElement = document.activeElement;
      const isTypingTarget =
        activeElement instanceof HTMLElement &&
        (activeElement.tagName === "INPUT" ||
          activeElement.tagName === "TEXTAREA" ||
          activeElement.isContentEditable);
      if (!isTypingTarget) {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      return;
    }
    if (!filteredItems.length) {
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Enter") {
      return;
    }
    event.preventDefault();

    const currentIndex = selectedId
      ? filteredItems.findIndex((item) => item.id === selectedId)
      : -1;
    if (event.key === "Enter") {
      const fallback = filteredItems[currentIndex >= 0 ? currentIndex : 0];
      if (fallback) {
        onOpenConfiguration(fallback.id);
      }
      return;
    }

    const direction = event.key === "ArrowDown" ? 1 : -1;
    const startIndex = currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = (startIndex + direction + filteredItems.length) % filteredItems.length;
    const next = filteredItems[nextIndex];
    if (!next) {
      return;
    }
    setSelectedId(next.id);
    rowButtonRefs.current.get(next.id)?.focus();
  };

  return (
    <section
      className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm"
      onKeyDown={handleKeyboardNavigation}
      aria-label="Configurations"
    >
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Configurations
        </p>
        <p className="text-sm text-muted-foreground">
          Open any configuration from this workspace, search quickly, archive drafts, or create a draft copy.
        </p>
      </div>

      <div className="relative">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={searchInputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search configurations"
          className="pl-9"
          aria-label="Search configurations"
        />
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-lg border border-border p-3">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="mt-2 h-3 w-60" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
          <p className="font-medium text-destructive">{errorMessage || "Unable to load configurations."}</p>
          <Button type="button" size="sm" variant="secondary" className="mt-3" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="rounded-lg border border-border bg-muted/20 p-5 text-sm text-muted-foreground">
          {query.trim().length > 0
            ? "No configurations match your search."
            : "No configurations yet. Create your first configuration or import one."}
        </div>
      ) : (
        <ul className="space-y-2.5">
          {filteredItems.map((item) => {
            const status = normalizeConfigStatus(item.status);
            const canArchiveDraft = status === "draft";
            const canSaveAsDraft = status !== "draft";
            const isSelected = selectedId === item.id;
            return (
              <li key={item.id} className="rounded-lg border border-border bg-background/70 p-3">
                <div className="flex items-start justify-between gap-3">
                  <button
                    ref={(node) => rowButtonRefs.current.set(item.id, node)}
                    type="button"
                    onClick={() => onOpenConfiguration(item.id)}
                    className="min-w-0 flex-1 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-semibold text-foreground" title={item.displayName}>
                        {item.displayName}
                      </p>
                      {item.isActive ? <Badge variant="secondary">Production</Badge> : null}
                      <StatusPill status={status} />
                      {isSelected ? <Badge variant="outline">Selected</Badge> : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Updated {formatTimestamp(item.updatedAt)}
                    </p>
                  </button>
                  <div className="flex items-center gap-2">
                    <Button type="button" size="sm" variant="secondary" onClick={() => onOpenConfiguration(item.id)}>
                      Open
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button type="button" size="icon" variant="ghost" aria-label={`Actions for ${item.displayName}`}>
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuItem onSelect={() => onOpenConfiguration(item.id)}>
                          Open
                        </DropdownMenuItem>
                        {canSaveAsDraft ? (
                          <DropdownMenuItem onSelect={() => onSaveAsNewDraft(item.id)}>
                            <CopyPlus className="h-4 w-4" />
                            Save as new draft
                          </DropdownMenuItem>
                        ) : null}
                        {canArchiveDraft ? (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onSelect={() => onArchiveDraft(item.id)}
                              disabled={isArchivingDraft}
                              variant="destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                              Archive draft
                            </DropdownMenuItem>
                          </>
                        ) : null}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "never";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return formatDistanceToNow(date, { addSuffix: true });
}
