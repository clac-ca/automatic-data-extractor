import clsx from "clsx";

import type { DocumentsFilters, SavedView } from "../types";
import { unassignedKey } from "./PeoplePicker";

type BuiltInViewId =
  | "all_documents"
  | "assigned_to_me"
  | "assigned_to_me_or_unassigned"
  | "unassigned"
  | "processed"
  | "processing"
  | "failed"
  | "archived"
  | "custom";

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
    assignedToMe: number;
    assignedToMeOrUnassigned: number;
    unassigned: number;
    processed: number;
    processing: number;
    failed: number;
    archived: number;
  };
}) {
  const builtins: { id: BuiltInViewId; label: string; count?: number }[] = [
    { id: "all_documents", label: "All documents", count: counts.total },
    { id: "assigned_to_me", label: "Assigned to me", count: counts.assignedToMe },
    {
      id: "assigned_to_me_or_unassigned",
      label: "Assigned to me or Unassigned",
      count: counts.assignedToMeOrUnassigned,
    },
    { id: "unassigned", label: "Unassigned", count: counts.unassigned },
    { id: "processed", label: "Processed", count: counts.processed },
    { id: "processing", label: "Processing", count: counts.processing },
    { id: "failed", label: "Failed", count: counts.failed },
    { id: "archived", label: "Archived", count: counts.archived },
  ];

  return (
    <aside className="flex min-h-0 min-w-0 w-full flex-col border-r border-border bg-card lg:w-72 lg:shrink-0">
      <div className="shrink-0 border-b border-border px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Views</p>
        <p className="mt-2 text-xs text-muted-foreground">
          Use views to focus work. Assignment and notes make this a shared workspace.
        </p>
        <button
          type="button"
          onClick={onOpenSaveDialog}
          className="mt-3 w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground hover:border-brand-300"
        >
          Save current view
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-auto px-2 py-3">
        <div className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
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
                activeViewId === view.id
                  ? "bg-brand-50 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200"
                  : "hover:bg-background dark:hover:bg-muted/40 text-foreground",
              )}
            >
              <span className="font-semibold">{view.label}</span>
              {typeof view.count === "number" ? (
                <span className="rounded-full border border-border bg-card px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
                  {view.count}
                </span>
              ) : null}
            </button>
          ))}
        </div>

        <div className="mt-6 px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Saved
        </div>
        {savedViews.length === 0 ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">No saved views yet. Save a view to reuse your filters.</div>
        ) : (
          <div className="flex flex-col gap-1">
            {savedViews
              .slice()
              .sort((a, b) => b.updatedAt - a.updatedAt)
              .map((view) => (
                <div key={view.id} className="group flex items-center justify-between rounded-xl px-3 py-2 hover:bg-background">
                  <button
                    type="button"
                  onClick={() => onSelectSavedView(view.id)}
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
                    onClick={() => onDeleteSavedView(view.id)}
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

      <div className="shrink-0 border-t border-border px-4 py-3 text-[11px] text-muted-foreground">
        Tip: Use <span className="font-semibold">Unassigned</span> to triage, then <span className="font-semibold">Pick up</span> to own.
      </div>
    </aside>
  );
}

export function filtersForBuiltInView(
  id:
    | "all_documents"
    | "assigned_to_me"
    | "assigned_to_me_or_unassigned"
    | "unassigned"
    | "processed"
    | "processing"
    | "failed"
    | "archived",
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
    case "all_documents":
      return cleared;
    case "assigned_to_me":
      return { ...cleared, assignees: [currentUserKey] };
    case "assigned_to_me_or_unassigned":
      return { ...cleared, assignees: [currentUserKey, unassignedKey()] };
    case "unassigned":
      return { ...cleared, assignees: [unassignedKey()] };
    case "processed":
      return { ...cleared, statuses: ["ready"] };
    case "processing":
      return { ...cleared, statuses: ["queued", "processing"] };
    case "failed":
      return { ...cleared, statuses: ["failed"] };
    case "archived":
      return { ...cleared, statuses: ["archived"] };
    default:
      return cleared;
  }
}
