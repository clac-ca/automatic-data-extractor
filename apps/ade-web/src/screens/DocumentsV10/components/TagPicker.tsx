import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { client } from "@shared/api/client";
import { Input } from "@ui/Input";

import type { components } from "@schema";

type TagCatalogPage = components["schemas"]["TagCatalogPage"];

export function TagPicker({
  workspaceId,
  selected,
  onToggle,
  placeholder,
  disabled,
}: {
  workspaceId: string;
  selected: string[];
  onToggle: (tag: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);

  const effectiveQuery = query.trim();
  const canSearch = effectiveQuery.length >= 2;

  const tagsQuery = useQuery<TagCatalogPage>({
    queryKey: ["documents-v10", workspaceId, "tags", { q: canSearch ? effectiveQuery : "" }],
    queryFn: async ({ signal }) => {
      const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/tags", {
        params: {
          path: { workspace_id: workspaceId },
          query: {
            q: canSearch ? effectiveQuery : null,
            sort: "-count",
            page: 1,
            page_size: 20,
            include_total: false,
          },
        },
        signal,
      });
      if (!data) throw new Error("Expected tag catalog page.");
      return data;
    },
    enabled: open && workspaceId.length > 0,
    staleTime: 30_000,
  });

  const items = tagsQuery.data?.items ?? [];

  const createCandidate = useMemo(() => {
    const t = effectiveQuery;
    if (!t) return null;
    const exact = items.some((i) => i.tag.toLowerCase() === t.toLowerCase());
    if (exact) return null;
    return t;
  }, [effectiveQuery, items]);

  useEffect(() => {
    if (!open) return;

    const onClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (containerRef.current && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        className={clsx(
          "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60",
          disabled
            ? "border-border bg-background text-muted-foreground"
            : "border-border bg-card text-foreground hover:bg-background",
        )}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {selected.length === 0 ? (
          <span className="text-muted-foreground">{placeholder}</span>
        ) : (
          <span>
            {selected.slice(0, 2).join(", ")}
            {selected.length > 2 ? ` +${selected.length - 2}` : ""}
          </span>
        )}
      </button>

      {open ? (
        <div
          className="absolute left-0 top-[calc(100%+0.5rem)] z-20 w-[18rem] rounded-2xl border border-border bg-card p-3 shadow-lg"
          data-ignore-row-click="true"
        >
          <div className="mb-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search or create tag…"
              className="h-9"
              autoFocus
            />
            <div className="mt-1 text-[11px] text-muted-foreground">
              Type 2+ characters to search existing tags.
            </div>
          </div>

          {selected.length ? (
            <div className="mb-2 flex flex-wrap gap-1">
              {selected.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => onToggle(t)}
                  className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-semibold text-foreground hover:text-rose-700"
                  title="Remove tag"
                >
                  {t} ×
                </button>
              ))}
            </div>
          ) : null}

          <div className="max-h-56 overflow-y-auto rounded-xl border border-border">
            {createCandidate ? (
              <button
                type="button"
                onClick={() => onToggle(createCandidate)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold text-foreground hover:bg-background"
              >
                <span>Create “{createCandidate}”</span>
                <span className="text-[11px] text-muted-foreground">new</span>
              </button>
            ) : null}

            {tagsQuery.isLoading ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">Loading tags…</div>
            ) : items.length === 0 ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">
                {canSearch ? "No matches." : "No tags yet."}
              </div>
            ) : (
              items.map((item) => {
                const isSelected = selected.includes(item.tag);
                return (
                  <button
                    key={item.tag}
                    type="button"
                    onClick={() => onToggle(item.tag)}
                    className={clsx(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold transition",
                      isSelected ? "bg-brand-50 text-foreground" : "text-foreground hover:bg-background",
                    )}
                  >
                    <span className="truncate">{item.tag}</span>
                    <span className="ml-3 text-[11px] text-muted-foreground">{item.document_count}</span>
                  </button>
                );
              })
            )}
          </div>

          <div className="mt-2 text-[11px] text-muted-foreground">
            Click a tag to toggle it.
          </div>
        </div>
      ) : null}
    </div>
  );
}
