import type { RunMetricsResource } from "@/pages/Workspace/sections/Documents/shared/types";

export type PreviewDisplayPreferences = {
  trimEmptyRows: boolean;
  trimEmptyColumns: boolean;
};

export const DEFAULT_PREVIEW_DISPLAY_PREFERENCES: PreviewDisplayPreferences = Object.freeze({
  trimEmptyRows: true,
  trimEmptyColumns: true,
});

export function isPreviewDisplayPreferences(value: unknown): value is PreviewDisplayPreferences {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return typeof candidate.trimEmptyRows === "boolean" && typeof candidate.trimEmptyColumns === "boolean";
}

type PreviewMetaLike = {
  totalRows: number;
  totalColumns: number;
  truncatedRows?: boolean;
  truncatedColumns?: boolean;
};

export type PreviewCountSummary = {
  totalRowsLabel: string;
  totalColumnsLabel: string;
  rowsVisibleLabel: string | null;
  columnsVisibleLabel: string | null;
  hasReduction: boolean;
};

export function buildPreviewCountSummary({
  previewMeta,
  visibleRowCount,
  visibleColumnCount,
}: {
  previewMeta: PreviewMetaLike | null;
  visibleRowCount: number;
  visibleColumnCount: number;
}): PreviewCountSummary | null {
  if (!previewMeta) {
    return null;
  }

  const rowsVisibleLabel = buildVisibleLabel({
    visible: visibleRowCount,
    total: previewMeta.totalRows,
    unit: "rows",
    truncated: previewMeta.truncatedRows,
  });
  const columnsVisibleLabel = buildVisibleLabel({
    visible: visibleColumnCount,
    total: previewMeta.totalColumns,
    unit: "columns",
    truncated: previewMeta.truncatedColumns,
  });

  return {
    totalRowsLabel: `${formatCount(previewMeta.totalRows)} rows`,
    totalColumnsLabel: `${formatCount(previewMeta.totalColumns)} columns`,
    rowsVisibleLabel,
    columnsVisibleLabel,
    hasReduction: Boolean(rowsVisibleLabel || columnsVisibleLabel),
  };
}

type BuildVisibleLabelInput = {
  visible: number;
  total: number;
  unit: "rows" | "columns";
  truncated?: boolean;
};

function buildVisibleLabel({ visible, total, unit, truncated = false }: BuildVisibleLabelInput): string | null {
  if (total <= 0) {
    return null;
  }

  if (visible < total) {
    return `Showing ${formatCount(visible)} of ${formatCount(total)} ${unit}`;
  }

  if (truncated) {
    return `Showing first ${formatCount(visible)} ${unit}`;
  }

  return null;
}

export type PreviewInlineStatTone = "neutral" | "success" | "warning" | "danger";

export type PreviewInlineStat = {
  id: "mappedColumns" | "validationIssues" | "nonEmptyRows" | "fieldCoverage";
  label: string;
  value: string;
  tone: PreviewInlineStatTone;
};

export function buildPreviewInlineStats(metrics: RunMetricsResource | null | undefined): PreviewInlineStat[] {
  if (!metrics) {
    return [];
  }

  const stats: PreviewInlineStat[] = [];

  const mappedColumnsStat = buildMappedColumnsStat(metrics);
  if (mappedColumnsStat) {
    stats.push(mappedColumnsStat);
  }

  const validationIssuesStat = buildValidationIssuesStat(metrics);
  if (validationIssuesStat) {
    stats.push(validationIssuesStat);
  }

  const nonEmptyRowsStat = buildNonEmptyRowsStat(metrics);
  if (nonEmptyRowsStat) {
    stats.push(nonEmptyRowsStat);
  }

  if (stats.length < 3) {
    const fieldCoverageStat = buildFieldCoverageStat(metrics);
    if (fieldCoverageStat) {
      stats.push(fieldCoverageStat);
    }
  }

  return stats.slice(0, 3);
}

function buildMappedColumnsStat(metrics: RunMetricsResource): PreviewInlineStat | null {
  const total = metrics.column_count_total;
  const mapped = metrics.column_count_mapped;

  if (typeof total !== "number" || total <= 0 || typeof mapped !== "number") {
    return null;
  }

  const boundedMapped = Math.min(Math.max(mapped, 0), total);
  const percentage = Math.round((boundedMapped / total) * 100);

  return {
    id: "mappedColumns",
    label: "Mapped columns",
    value: `${formatCount(boundedMapped)}/${formatCount(total)} (${percentage}%)`,
    tone: boundedMapped === total ? "success" : boundedMapped === 0 ? "warning" : "neutral",
  };
}

function buildValidationIssuesStat(metrics: RunMetricsResource): PreviewInlineStat | null {
  const total = metrics.validation_issues_total ?? metrics.evaluation_findings_total;
  if (typeof total !== "number") {
    return null;
  }

  const errors = metrics.validation_issues_error ?? metrics.evaluation_findings_error ?? 0;

  return {
    id: "validationIssues",
    label: "Validation issues",
    value: formatCount(total),
    tone: total === 0 ? "success" : errors > 0 ? "danger" : "warning",
  };
}

function buildNonEmptyRowsStat(metrics: RunMetricsResource): PreviewInlineStat | null {
  const total = metrics.row_count_total;
  const empty = metrics.row_count_empty;

  if (typeof total !== "number" || total <= 0 || typeof empty !== "number") {
    return null;
  }

  const nonEmpty = Math.max(total - empty, 0);
  const percentage = Math.round((nonEmpty / total) * 100);

  return {
    id: "nonEmptyRows",
    label: "Non-empty rows",
    value: `${formatCount(nonEmpty)}/${formatCount(total)} (${percentage}%)`,
    tone: nonEmpty === total ? "success" : nonEmpty === 0 ? "danger" : "neutral",
  };
}

function buildFieldCoverageStat(metrics: RunMetricsResource): PreviewInlineStat | null {
  const expected = metrics.field_count_expected;
  const detected = metrics.field_count_detected;

  if (typeof expected !== "number" || expected <= 0 || typeof detected !== "number") {
    return null;
  }

  const boundedDetected = Math.min(Math.max(detected, 0), expected);

  return {
    id: "fieldCoverage",
    label: "Detected fields",
    value: `${formatCount(boundedDetected)}/${formatCount(expected)}`,
    tone: boundedDetected === expected ? "success" : boundedDetected === 0 ? "warning" : "neutral",
  };
}

function formatCount(value: number): string {
  return value.toLocaleString();
}
