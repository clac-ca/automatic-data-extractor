import clsx from "clsx";

import type { DocumentsFilters, ListSettings, SavedView, ViewMode, WorkspacePerson } from "../types";
import type { BuiltInViewCounts, BuiltInViewId } from "../filters";
import type { PresenceParticipant } from "@hooks/presence";
import { AvatarStack, type AvatarStackItem } from "@components/ui/avatar-stack";
import { Button } from "@components/ui/button";
import { BoardIcon, GridIcon, RefreshIcon } from "@components/icons";
import { formatRelativeTime } from "../utils";
import { FiltersPopover } from "./FiltersPopover";
import { ListSettingsPopover } from "./ListSettingsPopover";
import { ViewsPopover } from "./ViewsPopover";

export function DocumentsFiltersBar({
  viewMode,
  onViewModeChange,
  listSettings,
  onListSettingsChange,
  workspaceId,
  filters,
  onChange,
  people,
  showingCount,
  totalCount,
  isRefreshing,
  lastUpdatedAt,
  now,
  onRefresh,
  presenceParticipants,
  activeViewId,
  onSetBuiltInView,
  savedViews,
  onSelectSavedView,
  onDeleteSavedView,
  onOpenSaveDialog,
  counts,
}: {
  viewMode: ViewMode;
  onViewModeChange: (value: ViewMode) => void;
  listSettings: ListSettings;
  onListSettingsChange: (next: ListSettings) => void;
  workspaceId: string;
  filters: DocumentsFilters;
  onChange: (next: DocumentsFilters) => void;
  people: WorkspacePerson[];
  showingCount: number;
  totalCount: number;
  isRefreshing: boolean;
  lastUpdatedAt: number | null;
  now: number;
  onRefresh: () => void;
  presenceParticipants: PresenceParticipant[];
  activeViewId: string;
  onSetBuiltInView: (id: BuiltInViewId) => void;
  savedViews: SavedView[];
  onSelectSavedView: (viewId: string) => void;
  onDeleteSavedView: (viewId: string) => void;
  onOpenSaveDialog: () => void;
  counts: BuiltInViewCounts;
}) {
  const activeCount =
    filters.statuses.length + filters.fileTypes.length + filters.tags.length + filters.assignees.length;
  const updatedLabel = lastUpdatedAt ? formatRelativeTime(now, lastUpdatedAt) : "—";
  const presenceItems: AvatarStackItem[] = presenceParticipants.map((participant) => ({
    id: participant.client_id,
    name: participant.display_name,
    email: participant.email,
  }));

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-6 py-3">
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
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2">
          {presenceParticipants.length > 0 ? (
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="flex h-2 w-2 rounded-full bg-success-500" aria-hidden />
              <AvatarStack items={presenceItems} size="xs" max={4} />
            </div>
          ) : null}

          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="hidden sm:inline">
              Updated {updatedLabel} · {showingCount} of {totalCount}
            </span>
            <span className="sm:hidden">
              {showingCount}/{totalCount}
            </span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onRefresh}
              className="h-6 w-6 rounded-full p-0 text-muted-foreground hover:text-foreground"
              aria-label="Refresh documents"
            >
              <RefreshIcon className={clsx("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
            </Button>
          </div>
        </div>

        <span className="h-5 w-px bg-border/70" aria-hidden />

        <div className="flex items-center gap-2">
          <ListSettingsPopover settings={listSettings} onChange={onListSettingsChange} />

          <div className="flex h-8 items-center rounded-lg border border-border bg-background px-1 text-sm shadow-sm">
            <Button
              type="button"
              size="sm"
              variant={viewMode === "grid" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("grid")}
              className={clsx("rounded-md px-3", viewMode === "grid" ? "shadow-sm" : "text-muted-foreground")}
              aria-pressed={viewMode === "grid"}
              aria-label="Grid view"
            >
              <GridIcon className="h-4 w-4" />
              Grid
            </Button>
            <Button
              type="button"
              size="sm"
              variant={viewMode === "board" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("board")}
              className={clsx("rounded-md px-3", viewMode === "board" ? "shadow-sm" : "text-muted-foreground")}
              aria-pressed={viewMode === "board"}
              aria-label="Board view"
            >
              <BoardIcon className="h-4 w-4" />
              Board
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
