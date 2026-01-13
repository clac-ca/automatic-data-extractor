import { useCallback, useEffect, useMemo } from "react";
import { parseAsInteger, parseAsString, parseAsStringEnum, useQueryState } from "nuqs";

import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { PageState } from "@components/layouts/page-state";

import { RunsMetrics } from "./components/RunsMetrics";
import { RunPreviewPanel } from "./components/RunPreviewPanel";
import { RunsTable } from "./components/RunsTable";
import { useRunsModel } from "./hooks/useRunsModel";
import type { RunRecord } from "./types";
import { useDataTable } from "@/hooks/use-data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { Button } from "@/components/ui/button";
import type { ColumnDef } from "@tanstack/react-table";
import { getValidFilters } from "@/lib/data-table";
import { getFiltersStateParser } from "@/lib/parsers";
import type { FilterJoinOperator } from "@api/listing";
import { RUNS_PAGE_SIZE } from "@api/runs/api";
import { getSortingStateParser } from "@/lib/parsers";

export default function RunsScreen() {
  const { workspace } = useWorkspaceContext();

  const [filtersValue, setFiltersValue] = useQueryState("filters", parseAsString);
  const [joinOperator] = useQueryState(
    "joinOperator",
    parseAsStringEnum(["and", "or"]).withDefault("and"),
  );
  const [runId, setRunId] = useQueryState("run", parseAsString);
  const [page] = useQueryState(
    "page",
    parseAsInteger.withDefault(1),
  );
  const [perPage] = useQueryState(
    "perPage",
    parseAsInteger.withDefault(RUNS_PAGE_SIZE),
  );

  const columns = useMemo<ColumnDef<RunRecord>[]>(() => {
    return [
      {
        id: "status",
        accessorKey: "status",
        enableSorting: true,
        enableColumnFilter: true,
        meta: {
          label: "Status",
          variant: "select",
          options: [
            { label: "Queued", value: "queued" },
            { label: "Running", value: "running" },
            { label: "Success", value: "succeeded" },
            { label: "Failed", value: "failed" },
          ],
        },
      },
      {
        id: "configurationId",
        accessorKey: "configurationId",
        enableSorting: false,
        enableColumnFilter: true,
        meta: { label: "Configuration", variant: "text" },
      },
      {
        id: "createdAt",
        accessorFn: (row) => row.raw.created_at,
        enableSorting: true,
        enableColumnFilter: true,
        meta: { label: "Created", variant: "dateRange" },
      },
      {
        id: "startedAt",
        accessorFn: (row) => row.raw.started_at ?? row.raw.created_at,
        enableSorting: true,
        enableColumnFilter: false,
        meta: { label: "Started", variant: "date" },
      },
      {
        id: "completedAt",
        accessorFn: (row) => row.raw.completed_at ?? null,
        enableSorting: true,
        enableColumnFilter: false,
        meta: { label: "Completed", variant: "date" },
      },
    ];
  }, []);

  const columnIds = useMemo(() => new Set(columns.map((column) => column.id).filter(Boolean) as string[]), [columns]);
  const [sorting] = useQueryState(
    "sort",
    getSortingStateParser<RunRecord>(columnIds)
      .withDefault([{ id: "createdAt", desc: true }]),
  );

  const normalizedFilters = useMemo(() => {
    if (!filtersValue) return [];
    const parsed =
      getFiltersStateParser<RunRecord>(columnIds).parse(filtersValue) ?? [];
    return getValidFilters(parsed);
  }, [filtersValue, columnIds]);

  const effectiveSort = sorting?.length ? JSON.stringify(sorting) : null;
  const query = useMemo(
    () => ({
      page,
      perPage,
      sort: effectiveSort,
      filters: normalizedFilters.length > 0 ? normalizedFilters : undefined,
      joinOperator: joinOperator as FilterJoinOperator,
    }),
    [page, perPage, effectiveSort, normalizedFilters, joinOperator],
  );

  const runsQueryModel = useRunsModel({ workspaceId: workspace.id, query });
  const expandedId = runsQueryModel.state.previewOpen ? runsQueryModel.state.activeId : null;
  const rangeLabel = normalizedFilters.length ? "Filtered results" : "All runs";

  const { table, debounceMs, throttleMs, shallow } = useDataTable({
    data: runsQueryModel.derived.runs,
    columns,
    pageCount: runsQueryModel.derived.pageCount,
    initialState: {
      sorting: [{ id: "createdAt", desc: true }],
      pagination: { pageSize: RUNS_PAGE_SIZE },
    },
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  useEffect(() => {
    table.setPageIndex(0);
  }, [filtersValue, table]);

  const handleClosePreview = useCallback(() => {
    runsQueryModel.actions.closePreview();
    setRunId(null);
  }, [runsQueryModel.actions, setRunId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (!runsQueryModel.state.previewOpen) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      handleClosePreview();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleClosePreview, runsQueryModel.state.previewOpen]);

  const handleTogglePreview = (id: string) => {
    if (runsQueryModel.state.previewOpen && runsQueryModel.state.activeId === id) {
      handleClosePreview();
      return;
    }
    runsQueryModel.actions.openPreview(id);
    setRunId(id);
  };

  const handleFiltersReset = useCallback(() => {
    table.resetSorting();
    table.setPageIndex(0);
    setFiltersValue(null);
  }, [setFiltersValue, table]);

  useEffect(() => {
    if (!runId) {
      if (runsQueryModel.state.previewOpen) {
        runsQueryModel.actions.closePreview();
      }
      return;
    }
    if (runsQueryModel.state.activeId !== runId || !runsQueryModel.state.previewOpen) {
      runsQueryModel.actions.openPreview(runId);
    }
  }, [runId, runsQueryModel.actions, runsQueryModel.state.activeId, runsQueryModel.state.previewOpen]);

  return (
    <div className="runs flex min-h-0 flex-1 flex-col bg-background text-foreground">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <RunsMetrics counts={runsQueryModel.derived.counts} rangeLabel={rangeLabel} />

          <DataTableAdvancedToolbar table={table}>
            <DataTableSortList table={table} align="start" />
            <DataTableFilterList
              table={table}
              align="start"
              debounceMs={debounceMs}
              throttleMs={throttleMs}
              shallow={shallow}
            />
            <div className="ml-auto flex flex-wrap items-center gap-3">
              <div className="text-xs text-muted-foreground">
                Showing <span className="font-semibold text-foreground">{runsQueryModel.derived.visibleRuns.length}</span>{" "}
                of <span className="font-semibold text-foreground">{runsQueryModel.derived.totalCount}</span>
              </div>
              <Button size="sm" variant="ghost" onClick={handleFiltersReset}>
                Reset
              </Button>
            </div>
          </DataTableAdvancedToolbar>

          {runsQueryModel.derived.isLoading ? (
            <div className="flex-1 bg-card px-6 py-10">
              <PageState title="Loading runs" variant="loading" />
            </div>
          ) : runsQueryModel.derived.isError ? (
            <div className="flex-1 bg-card px-6 py-10">
              <PageState
                title="Unable to load runs"
                description="Refresh the page or try again later."
                variant="error"
              />
            </div>
          ) : runsQueryModel.derived.visibleRuns.length === 0 ? (
            <div className="flex-1 bg-card px-6 py-10">
              <PageState
                title="No runs found"
                description="Try adjusting filters or clearing them."
                variant="empty"
              />
            </div>
          ) : (
            <RunsTable
              runs={runsQueryModel.derived.visibleRuns}
              activeId={expandedId}
              onSelect={handleTogglePreview}
              onNavigate={runsQueryModel.actions.setActiveId}
              expandedId={expandedId}
              expandedContent={
                runsQueryModel.state.previewOpen && runsQueryModel.derived.activeRun ? (
                  <RunPreviewPanel
                    run={runsQueryModel.derived.activeRun}
                    metrics={runsQueryModel.derived.metrics}
                    metricsLoading={runsQueryModel.derived.metricsLoading}
                    metricsError={runsQueryModel.derived.metricsError}
                    fields={runsQueryModel.derived.fields}
                    fieldsLoading={runsQueryModel.derived.fieldsLoading}
                    fieldsError={runsQueryModel.derived.fieldsError}
                    columns={runsQueryModel.derived.columns}
                    columnsLoading={runsQueryModel.derived.columnsLoading}
                    columnsError={runsQueryModel.derived.columnsError}
                    onClose={handleClosePreview}
                  />
                ) : null
              }
            />
          )}
          <div className="bg-card px-6 pb-4">
            <DataTablePagination table={table} />
          </div>
        </section>
      </div>
    </div>
  );
}
