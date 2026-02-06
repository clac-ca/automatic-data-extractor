import { useCallback, useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";

import { PageState } from "@/components/layout";
import { SpinnerIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";

import { useRunsListParams } from "../../hooks/useRunsListParams";
import { useRunsView } from "../../hooks/useRunsView";
import { RunsMetrics } from "../metrics/RunsMetrics";
import { RunPreviewPanel } from "../preview/RunPreviewPanel";
import { RunsTable } from "./RunsTable";
import { useRunsColumns } from "./runsColumns";

export function RunsTableView({ workspaceId }: { workspaceId: string }) {
  const { page, perPage, sort, filters, joinOperator } = useRunsListParams();
  const [activeRunId, setActiveRunId] = useQueryState("run", parseAsString);

  const runsView = useRunsView({
    workspaceId,
    page,
    perPage,
    sort,
    filters,
    joinOperator,
    activeRunId,
    enabled: Boolean(workspaceId),
  });

  const {
    runs,
    counts,
    pageCount,
    totalCount,
    isLoading,
    isFetching,
    isError,
    error,
    activeRun,
    metrics,
    metricsLoading,
    metricsError,
    fields,
    fieldsLoading,
    fieldsError,
    columns,
    columnsLoading,
    columnsError,
    refetch,
  } = runsView;

  const rangeLabel = filters?.length ? "Filtered results" : "All runs";
  const hasRuns = runs.length > 0;
  const showInitialLoading = isLoading && !hasRuns;
  const showInitialError = isError && !hasRuns;

  const handleTogglePreview = useCallback(
    (runId: string) => {
      setActiveRunId(activeRunId === runId ? null : runId);
    },
    [activeRunId, setActiveRunId],
  );

  const handleClosePreview = useCallback(() => {
    setActiveRunId(null);
  }, [setActiveRunId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (!activeRunId) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      handleClosePreview();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeRunId, handleClosePreview]);

  const columnsDef = useRunsColumns({
    activeRunId: activeRunId ?? null,
    onTogglePreview: handleTogglePreview,
  });

  const toolbarStatus = (
    <div className="flex h-4 w-4 items-center justify-center">
      {isFetching ? (
        <SpinnerIcon className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : isError && hasRuns ? (
        <AlertTriangle
          className="h-4 w-4 text-destructive"
          aria-label="Run list refresh failed"
        />
      ) : null}
    </div>
  );

  const toolbarActions = (
    <>
      <div className="text-xs text-muted-foreground">
        Showing <span className="font-semibold text-foreground">{runs.length}</span> of{" "}
        <span className="font-semibold text-foreground">{totalCount}</span>
      </div>
      {toolbarStatus}
    </>
  );

  if (showInitialLoading) {
    return (
      <div className="min-h-[240px]">
        <PageState title="Loading runs" variant="loading" />
      </div>
    );
  }

  if (showInitialError) {
    return (
      <div className="min-h-[240px]">
        <PageState
          title="Unable to load runs"
          description={error ?? "Refresh the page or try again later."}
          variant="error"
          action={
            <Button variant="secondary" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <RunsMetrics counts={counts} rangeLabel={rangeLabel} />
      <RunsTable
        data={runs}
        columns={columnsDef}
        pageCount={pageCount}
        toolbarActions={toolbarActions}
      />
      {activeRun ? (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <RunPreviewPanel
            run={activeRun}
            metrics={metrics}
            metricsLoading={metricsLoading}
            metricsError={metricsError}
            fields={fields}
            fieldsLoading={fieldsLoading}
            fieldsError={fieldsError}
            columns={columns}
            columnsLoading={columnsLoading}
            columnsError={columnsError}
            onClose={handleClosePreview}
          />
        </div>
      ) : null}
    </div>
  );
}
