import clsx from "clsx";
import type { DocumentStatus, DocumentsSavedView } from "../types";
import { formatRelativeTime } from "../utils";

type BuiltInViewId = "all" | "ready" | "processing" | "failed";

export function DocumentsSidebar({
  activeViewKey,
  onSelectBuiltIn,
  savedViews,
  onSelectSavedView,
  onDeleteSavedView,
  statusCounts,
  now,
}: {
  activeViewKey: string;
  onSelectBuiltIn: (id: BuiltInViewId) => void;
  savedViews: DocumentsSavedView[];
  onSelectSavedView: (viewId: string) => void;
  onDeleteSavedView: (viewId: string) => void;
  statusCounts: Record<DocumentStatus, number>;
  now: number;
}) {
  const builtins: { id: BuiltInViewId; label: string; count?: number }[] = [
    { id: "all", label: "All documents", count: Object.values(statusCounts).reduce((a, b) => a + b, 0) },
    { id: "ready", label: "Ready", count: statusCounts.ready },
    { id: "processing", label: "Processing", count: statusCounts.processing + statusCounts.queued },
    { id: "failed", label: "Failed", count: statusCounts.failed },
  ];

  return (
    <aside className="hidden min-h-0 w-[18rem] flex-col border-r border-slate-200 bg-white lg:flex">
      <div className="border-b border-slate-200 px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Library</p>
        <p className="mt-1 text-sm text-slate-600">Browse, tag, download, and reprocess.</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
        <div className="px-2 pb-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Views</p>
        </div>

        <div className="flex flex-col gap-1">
          {builtins.map((item) => {
            const key = `builtin:${item.id}`;
            const isActive = activeViewKey === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => onSelectBuiltIn(item.id)}
                className={clsx(
                  "flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
                  isActive ? "bg-brand-50 text-slate-900" : "text-slate-700 hover:bg-slate-50",
                )}
              >
                <span className="font-semibold">{item.label}</span>
                <span className={clsx("text-xs", isActive ? "text-slate-700" : "text-slate-400")}>
                  {item.count ?? 0}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-6 px-2 pb-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Saved</p>
        </div>

        {savedViews.length === 0 ? (
          <div className="px-3 py-2 text-sm text-slate-500">
            No saved views yet.
            <div className="mt-1 text-xs text-slate-400">Tip: apply filters, then click “Save view”.</div>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {savedViews
              .slice()
              .sort((a, b) => b.updatedAt - a.updatedAt)
              .map((view) => {
                const isActive = activeViewKey === `saved:${view.id}`;
                return (
                  <div
                    key={view.id}
                    className={clsx(
                      "group flex items-center justify-between rounded-xl px-3 py-2 transition",
                      isActive ? "bg-brand-50" : "hover:bg-slate-50",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectSavedView(view.id)}
                      className="min-w-0 flex-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
                    >
                      <div className={clsx("truncate text-sm font-semibold", isActive ? "text-slate-900" : "text-slate-700")}>
                        {view.name}
                      </div>
                      <div className="text-xs text-slate-400">Updated {formatRelativeTime(now, view.updatedAt)}</div>
                    </button>

                    <button
                      type="button"
                      onClick={() => onDeleteSavedView(view.id)}
                      className="ml-2 hidden rounded-md px-2 py-1 text-xs font-semibold text-slate-500 hover:bg-white hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 group-hover:block group-focus-within:block"
                      title="Delete view"
                    >
                      Delete
                    </button>
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </aside>
  );
}
