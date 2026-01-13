import type { RunResource } from "@schema";
import type { RunMetrics, RunRecord, RunsCounts } from "./types";

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


export function buildCounts(runs: RunRecord[]): RunsCounts {
  let warningKnown = false;
  const counts: {
    total: number;
    success: number;
    warning: number | null;
    failed: number;
    running: number;
    queued: number;
    active: number;
  } = {
    total: 0,
    success: 0,
    warning: null,
    failed: 0,
    running: 0,
    queued: 0,
    active: 0,
  };

  runs.forEach((run) => {
    counts.total += 1;
    if (run.status === "succeeded") counts.success += 1;
    if (run.status === "failed") counts.failed += 1;
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

export function buildRunRecord(run: RunResource): RunRecord {
  const inputName = run.input?.filename ?? run.input?.document_id ?? `Run ${run.id}`;
  const outputName = run.output?.filename ?? null;
  const startedAtLabel = formatTimestamp(run.started_at ?? run.created_at);
  const durationLabel = formatDuration(run.duration_seconds ?? null, run.status);
  const configLabel = run.configuration_id ?? "—";

  return {
    id: run.id,
    configurationId: run.configuration_id,
    status: run.status,
    inputName,
    outputName,
    configLabel,
    startedAtLabel,
    durationLabel,
    rows: null,
    warnings: null,
    errors: null,
    quality: null,
    ownerLabel: "—",
    triggerLabel: "—",
    engineLabel: "—",
    regionLabel: "—",
    notes: run.failure_message ?? null,
    raw: run,
  };
}
