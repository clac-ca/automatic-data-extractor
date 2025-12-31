import type {
  RunMetrics,
  RunRecord,
  RunsCounts,
  RunsDateRange,
  RunsStatusFilter,
} from "./types";

const numberFormatter = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return numberFormatter.format(value);
}

export function formatQuality(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value}%`;
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

export function computeMappingQuality(metrics: RunMetrics | null | undefined): number | null {
  if (!metrics) return null;
  const expected = metrics.field_count_expected ?? null;
  const detected = metrics.field_count_detected ?? null;
  if (!expected || expected <= 0 || detected === null) return null;
  return Math.round((detected / expected) * 100);
}

export function formatDuration(seconds: number | null | undefined, status: RunRecord["status"]): string {
  if (typeof seconds === "number" && Number.isFinite(seconds)) {
    const minutes = Math.floor(seconds / 60);
    const remaining = Math.round(seconds % 60);
    if (minutes <= 0) return `${remaining}s`;
    return `${minutes}m ${remaining}s`;
  }

  if (status === "queued") return "Queued";
  if (status === "running") return "Running";
  if (status === "cancelled") return "Cancelled";

  return "—";
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function formatResultLabel(run: RunRecord): string {
  if (run.warnings === 0 && run.errors === 0) return "Clean";
  if (typeof run.errors === "number" && run.errors > 0) return `${run.errors} errors`;
  if (typeof run.warnings === "number") return `${run.warnings} warnings`;
  return "—";
}

export function coerceStatus(value: string | null): RunsStatusFilter {
  if (!value || value === "all") return "all";
  if (["queued", "running", "succeeded", "failed", "cancelled"].includes(value)) {
    return value as RunsStatusFilter;
  }
  return "all";
}

export function coerceDateRange(value: string | null): RunsDateRange {
  if (!value) return "14d";
  if (["14d", "7d", "24h", "30d", "custom"].includes(value)) return value as RunsDateRange;
  return "14d";
}

export function buildCounts(runs: RunRecord[]): RunsCounts {
  let warningKnown = false;
  const counts: {
    total: number;
    success: number;
    warning: number | null;
    failed: number;
    running: number;
    queued: number;
    cancelled: number;
    active: number;
  } = {
    total: 0,
    success: 0,
    warning: null,
    failed: 0,
    running: 0,
    queued: 0,
    cancelled: 0,
    active: 0,
  };

  runs.forEach((run) => {
    counts.total += 1;
    if (run.status === "succeeded") counts.success += 1;
    if (run.status === "failed") counts.failed += 1;
    if (run.status === "cancelled") counts.cancelled += 1;
    if (run.status === "running") counts.running += 1;
    if (run.status === "queued") counts.queued += 1;

    if (typeof run.warnings === "number") {
      warningKnown = true;
      counts.warning = (counts.warning ?? 0) + run.warnings;
    }
  });

  counts.active = counts.running + counts.queued;
  if (!warningKnown) counts.warning = null;
  return counts;
}

export function buildCreatedAtRange(range: RunsDateRange, now = new Date()) {
  if (range === "custom") {
    return {};
  }
  const end = new Date(now);
  const start = new Date(now);
  if (range === "24h") {
    start.setHours(start.getHours() - 24);
  } else if (range === "7d") {
    start.setDate(start.getDate() - 7);
  } else if (range === "30d") {
    start.setDate(start.getDate() - 30);
  } else {
    start.setDate(start.getDate() - 14);
  }

  return {
    created_after: start.toISOString(),
    created_before: end.toISOString(),
  };
}
