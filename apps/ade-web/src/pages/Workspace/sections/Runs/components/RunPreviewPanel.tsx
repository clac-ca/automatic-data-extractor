import { useMemo, useState } from "react";
import clsx from "clsx";

import { Button } from "@components/Button";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@components/Tabs";

import { RUN_STATUS_META } from "../constants";
import { computeMappingQuality, formatNumber, formatQuality, formatScore } from "../utils";
import type { RunColumn, RunField, RunMetrics, RunRecord } from "../types";

type InspectorTab = "summary" | "metrics" | "fields" | "columns";

type RunPreviewPanelProps = {
  run: RunRecord;
  onClose?: () => void;
  metrics: RunMetrics | null;
  metricsLoading: boolean;
  metricsError: boolean;
  fields: RunField[] | null;
  fieldsLoading: boolean;
  fieldsError: boolean;
  columns: RunColumn[] | null;
  columnsLoading: boolean;
  columnsError: boolean;
};

export function RunPreviewPanel({
  run,
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
}: RunPreviewPanelProps) {
  const [tab, setTab] = useState<InspectorTab>("summary");

  const summary = useMemo(() => {
    const warnings =
      metrics?.validation_issues_warning ??
      metrics?.evaluation_findings_warning ??
      run.warnings ??
      null;
    const errors =
      metrics?.validation_issues_error ??
      metrics?.evaluation_findings_error ??
      run.errors ??
      null;
    const rows = metrics?.row_count_total ?? run.rows ?? null;
    const quality = computeMappingQuality(metrics) ?? run.quality ?? null;

    return { warnings, errors, rows, quality };
  }, [metrics, run.errors, run.quality, run.rows, run.warnings]);

  const warningsLabel =
    summary.warnings === null
      ? "Warnings data unavailable"
      : `${formatNumber(summary.warnings)} warnings detected`;
  const errorsLabel =
    summary.errors === null
      ? "Errors data unavailable"
      : `${formatNumber(summary.errors)} errors detected`;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span
            className={clsx(
              "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
              RUN_STATUS_META[run.status].badgeClass,
            )}
          >
            {RUN_STATUS_META[run.status].label}
          </span>
          <h3 className="mt-2 text-base font-semibold text-foreground">{run.inputName}</h3>
          <p className="text-xs text-muted-foreground">{run.id}</p>
        </div>
        <div className="flex items-start gap-3 text-xs text-muted-foreground">
          <div>
            <p>{run.startedAtLabel}</p>
            <p>{run.durationLabel}</p>
          </div>
          {onClose ? (
            <Button size="sm" variant="ghost" onClick={onClose}>
              Close preview
            </Button>
          ) : null}
        </div>
      </div>

      <TabsRoot value={tab} onValueChange={(value) => setTab(value as InspectorTab)}>
        <TabsList className="mt-4 flex flex-wrap gap-2 border-b border-border pb-2">
          <TabButton value="summary" label="Summary" active={tab === "summary"} />
          <TabButton value="metrics" label="Metrics" active={tab === "metrics"} />
          <TabButton value="fields" label="Fields" active={tab === "fields"} />
          <TabButton value="columns" label="Columns" active={tab === "columns"} />
        </TabsList>

        <TabsContent value="summary" className="mt-4">
          <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
            <div>
              <div className="grid gap-2 sm:grid-cols-4">
                <MiniMetric label="Rows" value={formatNumber(summary.rows)} />
                <MiniMetric label="Quality" value={formatQuality(summary.quality)} />
                <MiniMetric label="Warnings" value={formatNumber(summary.warnings)} />
                <MiniMetric label="Errors" value={formatNumber(summary.errors)} />
              </div>
              <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                <DetailRow label="Output" value={run.outputName ?? "Output not available"} />
                <DetailRow label="Config" value={run.configLabel} />
                <DetailRow label="Trigger" value={run.triggerLabel} />
                <DetailRow label="Engine" value={run.engineLabel} />
                <DetailRow label="Region" value={run.regionLabel} />
                <DetailRow label="Owner" value={run.ownerLabel} />
              </div>
            </div>
            <div className="rounded-xl border border-border bg-background p-3">
              <h4 className="text-sm font-semibold text-foreground">Quick issues</h4>
              <ul className="mt-3 space-y-2 text-xs text-muted-foreground">
                <li className="rounded-lg border border-border bg-card px-2 py-2">{warningsLabel}</li>
                <li className="rounded-lg border border-border bg-card px-2 py-2">{errorsLabel}</li>
                <li className="rounded-lg border border-border bg-card px-2 py-2">
                  Notes: {run.notes ?? "No notes captured"}
                </li>
              </ul>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary">
                  View logs
                </Button>
                <Button size="sm" variant="ghost">
                  Open output
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="metrics" className="mt-4">
          <MetricsTab metrics={metrics} loading={metricsLoading} error={metricsError} />
        </TabsContent>

        <TabsContent value="fields" className="mt-4">
          <FieldsTab fields={fields} loading={fieldsLoading} error={fieldsError} />
        </TabsContent>

        <TabsContent value="columns" className="mt-4">
          <ColumnsTab columns={columns} loading={columnsLoading} error={columnsError} />
        </TabsContent>
      </TabsRoot>
    </div>
  );
}

function MetricsTab({
  metrics,
  loading,
  error,
}: {
  metrics: RunMetrics | null;
  loading: boolean;
  error: boolean;
}) {
  if (loading) {
    return <TabState title="Loading metrics" description="Fetching run metrics and validation summary." />;
  }
  if (error) {
    return <TabState title="Unable to load metrics" description="Refresh the page or try again later." />;
  }
  if (!metrics) {
    return (
      <TabState
        title="Metrics not available yet"
        description="Metrics appear after the run completes and the engine summary is captured."
      />
    );
  }

  const fieldCoverage = computeMappingQuality(metrics);
  const evaluationItems = [
    { label: "Outcome", value: metrics.evaluation_outcome ?? "—" },
    { label: "Findings total", value: formatNumber(metrics.evaluation_findings_total) },
    { label: "Findings info", value: formatNumber(metrics.evaluation_findings_info) },
    { label: "Findings warning", value: formatNumber(metrics.evaluation_findings_warning) },
    { label: "Findings error", value: formatNumber(metrics.evaluation_findings_error) },
  ];

  const validationItems = [
    { label: "Issues total", value: formatNumber(metrics.validation_issues_total) },
    { label: "Info", value: formatNumber(metrics.validation_issues_info) },
    { label: "Warnings", value: formatNumber(metrics.validation_issues_warning) },
    { label: "Errors", value: formatNumber(metrics.validation_issues_error) },
    { label: "Max severity", value: metrics.validation_max_severity ?? "—" },
  ];

  const coverageItems = [
    { label: "Workbooks", value: formatNumber(metrics.workbook_count) },
    { label: "Sheets", value: formatNumber(metrics.sheet_count) },
    { label: "Tables", value: formatNumber(metrics.table_count) },
    { label: "Rows", value: formatNumber(metrics.row_count_total) },
    { label: "Empty rows", value: formatNumber(metrics.row_count_empty) },
    { label: "Columns", value: formatNumber(metrics.column_count_total) },
    { label: "Mapped columns", value: formatNumber(metrics.column_count_mapped) },
    { label: "Unmapped columns", value: formatNumber(metrics.column_count_unmapped) },
    {
      label: "Fields detected",
      value: `${formatNumber(metrics.field_count_detected)} / ${formatNumber(metrics.field_count_expected)}`,
    },
    { label: "Cells non-empty", value: formatNumber(metrics.cell_count_non_empty) },
    { label: "Cells total", value: formatNumber(metrics.cell_count_total) },
  ];

  return (
    <div className="grid gap-3">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <MiniMetric label="Evaluation" value={metrics.evaluation_outcome ?? "—"} />
        <MiniMetric label="Validation" value={metrics.validation_max_severity ?? "—"} />
        <MiniMetric label="Rows" value={formatNumber(metrics.row_count_total)} />
        <MiniMetric label="Field coverage" value={formatQuality(fieldCoverage)} />
      </div>
      <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr]">
        <MetricGroup title="Validation issues" items={validationItems} />
        <MetricGroup title="Evaluation findings" items={evaluationItems} />
      </div>
      <MetricGroup title="Structure and volume" items={coverageItems} />
    </div>
  );
}

function FieldsTab({
  fields,
  loading,
  error,
}: {
  fields: RunField[] | null;
  loading: boolean;
  error: boolean;
}) {
  if (loading) {
    return <TabState title="Loading field detection" description="Fetching per-field detection coverage." />;
  }
  if (error) {
    return <TabState title="Unable to load field detection" description="Refresh the page or try again later." />;
  }
  if (!fields) {
    return (
      <TabState
        title="Field detection not available"
        description="Field summaries appear once the run metrics are computed."
      />
    );
  }
  if (fields.length === 0) {
    return <TabState title="No fields detected" description="No fields were detected for this run." />;
  }

  const detectedCount = fields.filter((field) => field.detected).length;
  const notDetectedCount = fields.length - detectedCount;
  const coverage = fields.length > 0 ? Math.round((detectedCount / fields.length) * 100) : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <SummaryPill label="Total fields" value={formatNumber(fields.length)} />
        <SummaryPill label="Detected" value={formatNumber(detectedCount)} />
        <SummaryPill label="Not detected" value={formatNumber(notDetectedCount)} />
        <SummaryPill label="Coverage" value={formatQuality(coverage)} />
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-[1.6fr_120px_140px_120px_120px] border-b border-border bg-muted/40 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            <span>Field</span>
            <span>Status</span>
            <span>Best score</span>
            <span>Tables</span>
            <span>Columns</span>
          </div>
          {fields.map((field) => (
            <div key={field.field} className="border-b border-border/70 px-4 py-3">
              <div className="grid grid-cols-[1.6fr_120px_140px_120px_120px] items-center">
                <div>
                  <p className="text-sm font-semibold text-foreground">{field.label ?? field.field}</p>
                  <p className="text-xs text-muted-foreground">{field.field}</p>
                </div>
                <DetectionBadge detected={field.detected} />
                <span className="text-xs text-foreground">{formatScore(field.best_mapping_score)}</span>
                <span className="text-xs text-muted-foreground">{formatNumber(field.occurrences_tables)}</span>
                <span className="text-xs text-muted-foreground">{formatNumber(field.occurrences_columns)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ColumnsTab({
  columns,
  loading,
  error,
}: {
  columns: RunColumn[] | null;
  loading: boolean;
  error: boolean;
}) {
  if (loading) {
    return <TabState title="Loading columns" description="Fetching detected column headers." />;
  }
  if (error) {
    return <TabState title="Unable to load columns" description="Refresh the page or try again later." />;
  }
  if (!columns) {
    return (
      <TabState
        title="Column mappings not available"
        description="Column details appear once the run metrics are computed."
      />
    );
  }
  if (columns.length === 0) {
    return <TabState title="No columns" description="No columns were detected for this run." />;
  }

  const statusCounts = columns.reduce(
    (acc, column) => {
      const status = normalizeColumnStatus(column.mapping_status);
      acc.total += 1;
      acc[status] = (acc[status] ?? 0) + 1;
      return acc;
    },
    { total: 0 } as Record<string, number>,
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <SummaryPill label="Total columns" value={formatNumber(statusCounts.total)} />
        {Object.entries(COLUMN_STATUS_META)
          .filter(([key]) => statusCounts[key])
          .map(([key, meta]) => (
            <SummaryPill key={key} label={meta.label} value={formatNumber(statusCounts[key])} />
          ))}
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[860px]">
          <div className="grid grid-cols-[1.5fr_1.4fr_140px_140px_120px_120px] border-b border-border bg-muted/40 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            <span>Location</span>
            <span>Header</span>
            <span>Status</span>
            <span>Mapped field</span>
            <span>Score</span>
            <span>Non-empty</span>
          </div>
          {columns.map((column, index) => {
            const sheetLabel = column.sheet_name ?? `Sheet ${column.sheet_index + 1}`;
            const tableLabel = `Table ${column.table_index + 1}`;
            const workbookLabel = column.workbook_name ?? `Workbook ${column.workbook_index + 1}`;
            const headerLabel = column.header_raw ?? column.header_normalized ?? "—";
            const normalized = column.header_normalized;
            const mappedField = column.mapped_field ?? "—";

            return (
              <div key={`${column.workbook_index}-${column.sheet_index}-${column.table_index}-${column.column_index}-${index}`} className="border-b border-border/70 px-4 py-3">
                <div className="grid grid-cols-[1.5fr_1.4fr_140px_140px_120px_120px] items-center">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{sheetLabel}</p>
                    <p className="text-xs text-muted-foreground">{workbookLabel} / {tableLabel}</p>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{headerLabel}</p>
                    {normalized && normalized !== headerLabel ? (
                      <p className="text-xs text-muted-foreground">{normalized}</p>
                    ) : null}
                  </div>
                  <MappingStatusBadge status={column.mapping_status} />
                  <span className="text-xs text-muted-foreground">{mappedField}</span>
                  <span className="text-xs text-muted-foreground">{formatScore(column.mapping_score)}</span>
                  <span className="text-xs text-muted-foreground">{formatNumber(column.non_empty_cells)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
      <span>{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

function MetricGroup({ title, items }: { title: string; items: { label: string; value: string }[] }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
            <span className="text-muted-foreground">{item.label}</span>
            <span className="text-foreground">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1">
      <span>{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </span>
  );
}

function DetectionBadge({ detected }: { detected: boolean }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center rounded-full px-2 py-1 text-[11px] font-semibold",
        detected ? "bg-success-100 text-success-700" : "bg-muted text-muted-foreground",
      )}
    >
      {detected ? "Detected" : "Not detected"}
    </span>
  );
}

const COLUMN_STATUS_META: Record<string, { label: string; className: string }> = {
  mapped: { label: "Mapped", className: "bg-success-100 text-success-700" },
  unmapped: { label: "Unmapped", className: "bg-muted text-muted-foreground" },
};

function MappingStatusBadge({ status }: { status?: string | null }) {
  const key = normalizeColumnStatus(status);
  const meta = COLUMN_STATUS_META[key];

  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center rounded-full px-2 py-1 text-[11px] font-semibold",
        meta.className,
      )}
    >
      {meta.label}
    </span>
  );
}

function normalizeColumnStatus(status?: string | null): "mapped" | "unmapped" {
  return status?.toLowerCase?.() === "mapped" ? "mapped" : "unmapped";
}

function TabButton({ value, label, active }: { value: InspectorTab; label: string; active: boolean }) {
  return (
    <TabsTrigger
      value={value}
      className={clsx(
        "rounded-full border px-3 py-1 text-xs font-semibold transition",
        active ? "border-transparent bg-brand-600 text-on-brand" : "border-border bg-background text-muted-foreground",
      )}
    >
      {label}
    </TabsTrigger>
  );
}

function TabState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-background px-4 py-4">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
    </div>
  );
}
