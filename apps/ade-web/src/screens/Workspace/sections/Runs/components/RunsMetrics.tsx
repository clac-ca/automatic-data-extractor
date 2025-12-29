import clsx from "clsx";

import type { RunsCounts } from "../types";
import { formatNumber } from "../utils";

export function RunsMetrics({ counts }: { counts: RunsCounts }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <MetricCard label="Total" value={formatNumber(counts.total)} meta="Last 14 days" />
      <MetricCard label="Success" value={formatNumber(counts.success)} meta="Completed" tone="success" />
      <MetricCard label="Warnings" value={formatNumber(counts.warning)} meta="Needs review" tone="warning" />
      <MetricCard label="Failed" value={formatNumber(counts.failed)} meta="Blocked" tone="danger" />
      <MetricCard label="Active" value={formatNumber(counts.active)} meta="Queued + running" tone="info" />
    </div>
  );
}

function MetricCard({
  label,
  value,
  meta,
  tone = "default",
}: {
  label: string;
  value: string;
  meta: string;
  tone?: "default" | "success" | "warning" | "danger" | "info";
}) {
  const toneClass =
    tone === "success"
      ? "text-success-700"
      : tone === "warning"
        ? "text-warning-700"
        : tone === "danger"
          ? "text-danger-700"
          : tone === "info"
            ? "text-info-700"
            : "text-foreground";

  return (
    <div className="rounded-2xl border border-border bg-card px-4 py-3 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={clsx("mt-1 text-xl font-semibold", toneClass)}>{value}</p>
      <p className="text-xs text-muted-foreground">{meta}</p>
    </div>
  );
}
