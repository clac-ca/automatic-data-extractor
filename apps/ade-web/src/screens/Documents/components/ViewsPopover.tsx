import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";

import type { SavedView } from "../types";

type BuiltInViewId = "all" | "mine" | "unassigned" | "ready" | "processing" | "failed";
type ActiveViewId = BuiltInViewId | "custom" | string;

export function ViewsPopover({
  activeViewId,
  onSetBuiltInView,
  savedViews,
  onSelectSavedView,
  onDeleteSavedView,
  onOpenSaveDialog,
  counts,
}: {
  activeViewId: ActiveViewId;
  onSetBuiltInView: (id: BuiltInViewId) => void;
  savedViews: SavedView[];
  onSelectSavedView: (viewId: string) => void;
  onDeleteSavedView: (viewId: string) => void;
  onOpenSaveDialog: () => void;
  counts: {
    total: number;
    mine: number;
    unassigned: number;
    ready: number;
    processing: number;
    failed: number;
  };
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (!open) return;
      const target = event.target as Node | null;
      if (containerRef.current && target && !containerRef.current.contains(target)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClickOutside);
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const builtins = useMemo(() => {
    return [
      { id: "all", label: "All documents", count: counts.total },
      { id: "mine", label: "Mine", count: counts.mine },
      { id: "unassigned", label: "Unassigned", count: counts.unassigned },
      { id: "ready", label: "Ready", count: counts.ready },
      { id: "processing", label: "Processing", count: counts.processing },
      { id: "failed", label: "Failed", count: counts.failed },
    ] as const;
  }, [counts.failed, counts.mine, counts.processing, counts.ready, counts.total, counts.unassigned]);

  const activeLabel = useMemo(() => {
    if (activeViewId === "custom") return "Custom view";
    const builtIn = builtins.find((view) => view.id === activeViewId);
    if (builtIn) return builtIn.label;
    const saved = savedViews.find((view) => view.id === activeViewId);
    return saved?.name ?? "Views";
  }, [activeViewId, builtins, savedViews]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm hover:border-brand-300"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <span>Views</span>
        <span className="max-w-[10rem] truncate text-[11px] font-medium text-muted-foreground">{activeLabel}</span>
        <span className="text-muted-foreground" aria-hidden>
          v
        </span>
      </button>

      {open ? (
        <div className="absolute left-0 z-30 mt-2 w-[22rem] rounded-2xl border border-border bg-card p-4 shadow-lg">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Views</p>
              <p className="mt-1 text-xs text-muted-foreground">Switch between built-in and saved views.</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onOpenSaveDialog();
              }}
              className="rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground hover:border-brand-300"
            >
              Save current view
            </button>
          </div>

          {activeViewId === "custom" ? (
            <div className="mt-3 rounded-xl border border-dashed border-border bg-background px-3 py-2 text-xs text-muted-foreground">
              You are on a custom view. Save it to reuse later.
            </div>
          ) : null}

          <div className="mt-4">
            <div className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Built-in
            </div>
            <div className="flex flex-col gap-1">
              {builtins.map((view) => (
                <button
                  key={view.id}
                  type="button"
                  onClick={() => {
                    onSetBuiltInView(view.id);
                    setOpen(false);
                  }}
                  className={clsx(
                    "flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition",
                    activeViewId === view.id
                      ? "bg-brand-50 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200"
                      : "hover:bg-background dark:hover:bg-muted/40 text-foreground",
                  )}
                >
                  <span className="font-semibold">{view.label}</span>
                  <span className="rounded-full border border-border bg-card px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
                    {view.count}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <div className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Saved
            </div>
            {savedViews.length === 0 ? (
              <div className="px-3 py-2 text-xs text-muted-foreground">No saved views yet.</div>
            ) : (
              <div className="flex flex-col gap-1">
                {savedViews
                  .slice()
                  .sort((a, b) => b.updatedAt - a.updatedAt)
                  .map((view) => (
                    <div key={view.id} className="group flex items-center justify-between rounded-xl px-3 py-2 hover:bg-background">
                      <button
                        type="button"
                        onClick={() => {
                          onSelectSavedView(view.id);
                          setOpen(false);
                        }}
                        className={clsx(
                          "min-w-0 flex-1 truncate text-left text-sm font-semibold",
                          activeViewId === view.id ? "text-brand-800 dark:text-brand-200" : "text-foreground",
                        )}
                        title={view.name}
                      >
                        {view.name}
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteSavedView(view.id);
                        }}
                        className="ml-2 hidden text-xs font-semibold text-muted-foreground hover:text-danger-600 group-hover:inline"
                        aria-label={`Delete view ${view.name}`}
                      >
                        Delete
                      </button>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
