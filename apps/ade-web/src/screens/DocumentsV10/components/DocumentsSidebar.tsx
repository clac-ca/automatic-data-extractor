import clsx from "clsx";

import type { DocumentsFilters, SavedView } from "../types";
import { unassignedKey } from "./PeoplePicker";

type BuiltInViewId = "all" | "mine" | "unassigned" | "ready" | "processing" | "failed" | "custom";

export function DocumentsSidebar({
  activeViewId,
  onSetBuiltInView,
  savedViews,
  onSelectSavedView,
  onDeleteSavedView,
  onOpenSaveDialog,
  counts,
}: {
  activeViewId: BuiltInViewId | string;
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
  const builtins: { id: BuiltInViewId; label: string; count?: number }[] = [
    { id: "all", label: "All documents", count: counts.total },
    { id: "mine", label: "Mine", count: counts.mine },
    { id: "unassigned", label: "Unassigned", count: counts.unassigned },
    { id: "ready", label: "Ready", count: counts.ready },
    { id: "processing", label: "Processing", count: counts.processing },
    { id: "failed", label: "Failed", count: counts.failed },
  ];

  return (
    <aside className="flex min-h-0 min-w-0 w-full flex-col border-r border-slate-200 bg-white lg:w-72 lg:shrink-0">
      <div className="shrink-0 border-b border-slate-200 px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Views</p>
        <p className="mt-2 text-xs text-slate-500">
          Use views to focus work. Assignment and notes make this a shared workspace.
        </p>
        <button
          type="button"
          onClick={onOpenSaveDialog}
          className="mt-3 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-brand-300"
        >
          Save current view
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-auto px-2 py-3">
        <div className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Built-in
        </div>
        <div className="flex flex-col gap-1">
          {builtins.map((view) => (
            <button
              key={view.id}
              type="button"
              onClick={() => onSetBuiltInView(view.id)}
              className={clsx(
                "flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition",
                activeViewId === view.id ? "bg-brand-50 text-brand-800" : "hover:bg-slate-50 text-slate-700",
              )}
            >
              <span className="font-semibold">{view.label}</span>
              {typeof view.count === "number" ? (
                <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-500">
                  {view.count}
                </span>
              ) : null}
            </button>
          ))}
        </div>

        <div className="mt-6 px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Saved
        </div>
        {savedViews.length === 0 ? (
          <div className="px-3 py-2 text-xs text-slate-500">No saved views yet. Save a view to reuse your filters.</div>
        ) : (
          <div className="flex flex-col gap-1">
            {savedViews
              .slice()
              .sort((a, b) => b.updatedAt - a.updatedAt)
              .map((view) => (
                <div key={view.id} className="group flex items-center justify-between rounded-xl px-3 py-2 hover:bg-slate-50">
                  <button
                    type="button"
                    onClick={() => onSelectSavedView(view.id)}
                    className={clsx(
                      "min-w-0 flex-1 truncate text-left text-sm font-semibold",
                      activeViewId === view.id ? "text-brand-800" : "text-slate-700",
                    )}
                    title={view.name}
                  >
                    {view.name}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteSavedView(view.id)}
                    className="ml-2 hidden text-xs font-semibold text-slate-400 hover:text-rose-600 group-hover:inline"
                    aria-label={`Delete view ${view.name}`}
                  >
                    Delete
                  </button>
                </div>
              ))}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-slate-200 px-4 py-3 text-[11px] text-slate-500">
        Tip: Use <span className="font-semibold">Unassigned</span> to triage, then <span className="font-semibold">Pick up</span> to own.
      </div>
    </aside>
  );
}

export function filtersForBuiltInView(
  id: "all" | "mine" | "unassigned" | "ready" | "processing" | "failed",
  base: DocumentsFilters,
  currentUserKey: string,
): DocumentsFilters {
  const cleared: DocumentsFilters = {
    ...base,
    statuses: [],
    fileTypes: [],
    tags: [],
    tagMode: "any",
    assignees: [],
  };

  switch (id) {
    case "all":
      return cleared;
    case "mine":
      return { ...cleared, assignees: [currentUserKey] };
    case "unassigned":
      return { ...cleared, assignees: [unassignedKey()] };
    case "ready":
      return { ...cleared, statuses: ["ready"] };
    case "processing":
      return { ...cleared, statuses: ["queued", "processing"] };
    case "failed":
      return { ...cleared, statuses: ["failed"] };
    default:
      return cleared;
  }
}
