import type { DocumentsFilters, SavedView, WorkspacePerson } from "../types";
import { FiltersPopover } from "./FiltersPopover";
import { ViewsPopover } from "./ViewsPopover";

export function DocumentsFiltersBar({
  workspaceId,
  filters,
  onChange,
  people,
  showingCount,
  totalCount,
  activeViewId,
  onSetBuiltInView,
  savedViews,
  onSelectSavedView,
  onDeleteSavedView,
  onOpenSaveDialog,
  counts,
}: {
  workspaceId: string;
  filters: DocumentsFilters;
  onChange: (next: DocumentsFilters) => void;
  people: WorkspacePerson[];
  showingCount: number;
  totalCount: number;
  activeViewId: string;
  onSetBuiltInView: (
    id:
      | "all_documents"
      | "assigned_to_me"
      | "assigned_to_me_or_unassigned"
      | "unassigned"
      | "processed"
      | "processing"
      | "failed"
      | "archived",
  ) => void;
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
  const activeCount =
    filters.statuses.length + filters.fileTypes.length + filters.tags.length + filters.assignees.length;

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <ViewsPopover
          activeViewId={activeViewId}
          onSetBuiltInView={onSetBuiltInView}
          savedViews={savedViews}
          onSelectSavedView={onSelectSavedView}
          onDeleteSavedView={onDeleteSavedView}
          onOpenSaveDialog={onOpenSaveDialog}
          counts={counts}
        />
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
            className="text-xs font-semibold text-muted-foreground hover:text-foreground"
          >
            Clear filters
          </button>
        ) : (
          <span className="text-xs text-muted-foreground">No filters applied</span>
        )}
      </div>

      <div className="text-xs text-muted-foreground">
        Showing <span className="font-semibold text-foreground">{showingCount}</span> of{" "}
        <span className="font-semibold text-foreground">{totalCount}</span>
      </div>
    </div>
  );
}
