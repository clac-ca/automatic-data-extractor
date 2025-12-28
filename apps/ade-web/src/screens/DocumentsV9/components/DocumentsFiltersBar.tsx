import type { DocumentsFilters, WorkspacePerson } from "../types";
import { FiltersPopover } from "./FiltersPopover";

export function DocumentsFiltersBar({
  workspaceId,
  filters,
  onChange,
  people,
  showingCount,
  totalCount,
}: {
  workspaceId: string;
  filters: DocumentsFilters;
  onChange: (next: DocumentsFilters) => void;
  people: WorkspacePerson[];
  showingCount: number;
  totalCount: number;
}) {
  const activeCount =
    filters.statuses.length + filters.fileTypes.length + filters.tags.length + filters.assignees.length;

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <FiltersPopover workspaceId={workspaceId} filters={filters} onChange={onChange} people={people} />

        {activeCount > 0 ? (
          <button
            type="button"
            onClick={() =>
              onChange({
                statuses: [],
                fileTypes: [],
                tags: [],
                tagMode: "any",
                assignees: [],
              })
            }
            className="text-xs font-semibold text-slate-500 hover:text-slate-700"
          >
            Clear filters
          </button>
        ) : (
          <span className="text-xs text-slate-400">No filters applied</span>
        )}
      </div>

      <div className="text-xs text-slate-500">
        Showing <span className="font-semibold text-slate-900">{showingCount}</span> of{" "}
        <span className="font-semibold text-slate-900">{totalCount}</span>
      </div>
    </div>
  );
}
