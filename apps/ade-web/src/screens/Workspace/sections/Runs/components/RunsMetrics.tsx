import clsx from "clsx";

import type { RunsCounts } from "../types";
import { formatNumber } from "../utils";

export function RunsMetrics({ counts }: { counts: RunsCounts }) {
  const completed = counts.success + counts.failed + counts.cancelled;
  const failedTotal = counts.failed + counts.cancelled;
  const successRate = completed > 0 ? Math.round((counts.success / completed) * 100) : 0;
  const warningsLabel = counts.warning === null ? "—" : formatNumber(counts.warning);

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr_1fr_1fr]">
        <SummaryBlock
          label="Active queue"
          value={formatNumber(counts.active)}
          meta={`${formatNumber(counts.running)} running · ${formatNumber(counts.queued)} queued`}
          tone="info"
        />
        <SummaryBlock
          label="Success rate"
          value={`${successRate}%`}
          meta={`${formatNumber(counts.success)} of ${formatNumber(completed)} completed`}
          tone="success"
        />
        <SummaryBlock
          label="Failed"
          value={formatNumber(failedTotal)}
          meta="Failed or cancelled runs"
          tone="danger"
        />
        <SummaryBlock
          label="Warnings"
          value={warningsLabel}
          meta="Validation warnings"
          tone="warning"
        />
      </div>
    </div>
  );
}

function SummaryBlock({
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
    <div className="rounded-xl border border-border bg-background px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={clsx("mt-1 text-2xl font-semibold", toneClass)}>{value}</p>
      <p className="text-xs text-muted-foreground">{meta}</p>
    </div>
  );
}
