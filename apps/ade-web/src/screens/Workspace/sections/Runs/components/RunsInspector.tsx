import { PageState } from "@ui/PageState";

import type { RunColumn, RunField, RunMetrics, RunRecord } from "../types";

import { RunPreviewPanel } from "./RunPreviewPanel";

export function RunsInspector({
  run,
  open,
  onClose,
  metrics,
  metricsLoading,
  metricsError,
  fields,
  fieldsLoading,
  fieldsError,
  columns,
  columnsLoading,
  columnsError,
}: {
  run: RunRecord | null;
  open: boolean;
  onClose: () => void;
  metrics: RunMetrics | null;
  metricsLoading: boolean;
  metricsError: boolean;
  fields: RunField[] | null;
  fieldsLoading: boolean;
  fieldsError: boolean;
  columns: RunColumn[] | null;
  columnsLoading: boolean;
  columnsError: boolean;
}) {
  if (!run || !open) {
    return (
      <section className="rounded-2xl border border-border bg-card px-6 py-8">
        <PageState
          title="Select a run"
          description="Choose a run from the table to inspect metrics, mappings, and output details."
          variant="empty"
        />
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <RunPreviewPanel
        run={run}
        metrics={metrics}
        metricsLoading={metricsLoading}
        metricsError={metricsError}
        fields={fields}
        fieldsLoading={fieldsLoading}
        fieldsError={fieldsError}
        columns={columns}
        columnsLoading={columnsLoading}
        columnsError={columnsError}
        onClose={onClose}
      />
    </section>
  );
}
