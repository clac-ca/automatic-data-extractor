import { useCallback, useEffect, useMemo } from "react";

import { useLocation, useNavigate } from "@app/nav/history";
import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { PageState } from "@ui/PageState";

import { RunsFiltersBar } from "./components/RunsFiltersBar";
import { RunsHeader } from "./components/RunsHeader";
import { RunsMetrics } from "./components/RunsMetrics";
import { RunPreviewPanel } from "./components/RunPreviewPanel";
import { RunsTable } from "./components/RunsTable";
import { DEFAULT_RUNS_FILTERS, DATE_RANGE_OPTIONS } from "./constants";
import { useRunsModel } from "./hooks/useRunsModel";
import { coerceDateRange, coerceResult, coerceStatus } from "./utils";
import type { RunsFilters } from "./types";

export default function WorkspaceRunsRoute() {
  const { workspace } = useWorkspaceContext();
  const location = useLocation();
  const navigate = useNavigate();

  const urlFilters = useMemo(() => parseFiltersFromSearch(location.search), [location.search]);
  const urlRunId = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("run");
  }, [location.search]);

  const model = useRunsModel({ workspaceId: workspace.id, initialFilters: urlFilters });
  const expandedId = model.state.previewOpen ? model.state.activeId : null;

  useEffect(() => {
    if (!filtersEqual(model.state.filters, urlFilters)) {
      model.actions.setFilters(urlFilters);
    }
  }, [model.actions, model.state.filters, urlFilters]);

  useEffect(() => {
    if (!urlRunId) {
      if (model.state.previewOpen) {
        model.actions.closePreview();
      }
      return;
    }
    if (model.state.activeId !== urlRunId || !model.state.previewOpen) {
      model.actions.openPreview(urlRunId);
    }
  }, [model.actions, model.state.activeId, model.state.previewOpen, urlRunId]);

  const syncUrl = useCallback(
    (filters: RunsFilters, runId: string | null) => {
      const params = buildSearchParams(filters, runId);
      const next = `${location.pathname}${params ? `?${params}` : ""}${location.hash ?? ""}`;
      const current = `${location.pathname}${location.search}${location.hash ?? ""}`;
      if (next === current) return;
      navigate(next, { replace: true });
    },
    [location.hash, location.pathname, location.search, navigate],
  );

  const handleClosePreview = useCallback(() => {
    model.actions.closePreview();
    syncUrl(model.state.filters, null);
  }, [model.actions, model.state.filters, syncUrl]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (!model.state.previewOpen) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      handleClosePreview();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleClosePreview, model.state.previewOpen]);

  const handleTogglePreview = (id: string) => {
    if (model.state.previewOpen && model.state.activeId === id) {
      handleClosePreview();
      return;
    }
    model.actions.openPreview(id);
    syncUrl(model.state.filters, id);
  };

  const handleFiltersChange = (next: Partial<RunsFilters>) => {
    const merged = { ...model.state.filters, ...next };
    model.actions.setFilters(merged);
    syncUrl(merged, model.state.previewOpen ? model.state.activeId : null);
  };

  const handleFiltersReset = () => {
    model.actions.resetFilters();
    syncUrl(DEFAULT_RUNS_FILTERS, model.state.previewOpen ? model.state.activeId : null);
  };

  return (
    <div className="runs flex min-h-0 flex-1 flex-col bg-background text-foreground">
      <RunsHeader
        onExport={() => {
          // TODO: Wire to export endpoint
        }}
        onStartRun={() => {
          // TODO: Wire to run creation flow
        }}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <RunsMetrics counts={model.derived.counts} rangeLabel={resolveRangeLabel(model.state.filters.dateRange)} />

          <RunsFiltersBar
            filters={model.state.filters}
            configOptions={model.derived.configOptions}
            ownerOptions={model.derived.ownerOptions}
            resultEnabled={model.derived.supportsResultFilters}
            counts={model.derived.counts}
            showingCount={model.derived.visibleRuns.length}
            totalCount={model.derived.totalCount}
            onChange={handleFiltersChange}
            onReset={handleFiltersReset}
          />

          {model.derived.isLoading ? (
            <div className="flex-1 bg-card px-6 py-10">
              <PageState title="Loading runs" variant="loading" />
            </div>
          ) : model.derived.isError ? (
            <div className="flex-1 bg-card px-6 py-10">
              <PageState
                title="Unable to load runs"
                description="Refresh the page or try again later."
                variant="error"
              />
            </div>
          ) : model.derived.visibleRuns.length === 0 ? (
            <div className="flex-1 bg-card px-6 py-10">
              <PageState
                title="No runs found"
                description="Try adjusting filters or clearing the search."
                variant="empty"
              />
            </div>
          ) : (
            <RunsTable
              runs={model.derived.visibleRuns}
              activeId={expandedId}
              onSelect={handleTogglePreview}
              onNavigate={model.actions.setActiveId}
              expandedId={expandedId}
              expandedContent={
                model.state.previewOpen && model.derived.activeRun ? (
                  <RunPreviewPanel
                    run={model.derived.activeRun}
                    metrics={model.derived.metrics}
                    metricsLoading={model.derived.metricsLoading}
                    metricsError={model.derived.metricsError}
                    fields={model.derived.fields}
                    fieldsLoading={model.derived.fieldsLoading}
                    fieldsError={model.derived.fieldsError}
                    columns={model.derived.columns}
                    columnsLoading={model.derived.columnsLoading}
                    columnsError={model.derived.columnsError}
                    onClose={handleClosePreview}
                  />
                ) : null
              }
            />
          )}
        </section>
      </div>
    </div>
  );
}

function parseFiltersFromSearch(search: string): RunsFilters {
  const params = new URLSearchParams(search);
  const searchValue = params.get("q") ?? DEFAULT_RUNS_FILTERS.search;
  const status = coerceStatus(params.get("status"));
  const result = coerceResult(params.get("result"));
  const dateRange = coerceDateRange(params.get("range"));
  const config = params.get("config") ?? DEFAULT_RUNS_FILTERS.config;
  const owner = params.get("owner") ?? DEFAULT_RUNS_FILTERS.owner;

  return {
    search: searchValue,
    status,
    result,
    dateRange,
    config,
    owner,
  };
}

function buildSearchParams(filters: RunsFilters, runId: string | null) {
  const params = new URLSearchParams();
  if (filters.search) params.set("q", filters.search);
  if (filters.status !== DEFAULT_RUNS_FILTERS.status) params.set("status", filters.status);
  if (filters.result !== DEFAULT_RUNS_FILTERS.result) params.set("result", filters.result);
  if (filters.dateRange !== DEFAULT_RUNS_FILTERS.dateRange) params.set("range", filters.dateRange);
  if (filters.config !== DEFAULT_RUNS_FILTERS.config) params.set("config", filters.config);
  if (filters.owner !== DEFAULT_RUNS_FILTERS.owner) params.set("owner", filters.owner);
  if (runId) params.set("run", runId);
  return params.toString();
}

function filtersEqual(a: RunsFilters, b: RunsFilters) {
  return (
    a.search === b.search &&
    a.status === b.status &&
    a.result === b.result &&
    a.dateRange === b.dateRange &&
    a.config === b.config &&
    a.owner === b.owner
  );
}

function resolveRangeLabel(value: RunsFilters["dateRange"]) {
  return DATE_RANGE_OPTIONS.find((option) => option.value === value)?.label ?? "Selected range";
}
