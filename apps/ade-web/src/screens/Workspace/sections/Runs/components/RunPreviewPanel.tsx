import clsx from "clsx";

import { Button } from "@ui/Button";

import { RUN_STATUS_META } from "../constants";
import { formatNumber, formatQuality } from "../utils";
import type { RunRecord } from "../types";

export function RunPreviewPanel({ run, onClose }: { run: RunRecord; onClose?: () => void }) {
  const warningsLabel =
    run.warnings === null ? "Warnings data unavailable" : `${formatNumber(run.warnings)} warnings detected`;
  const errorsLabel =
    run.errors === null ? "Errors data unavailable" : `${formatNumber(run.errors)} errors detected`;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
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

      <div className="mt-4 grid gap-3 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="grid gap-2 sm:grid-cols-4">
            <MiniMetric label="Rows" value={formatNumber(run.rows)} />
            <MiniMetric label="Quality" value={formatQuality(run.quality ?? null)} />
            <MiniMetric label="Warnings" value={formatNumber(run.warnings)} />
            <MiniMetric label="Errors" value={formatNumber(run.errors)} />
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
            <li className="rounded-lg border border-border bg-card px-2 py-2">
              {warningsLabel}
            </li>
            <li className="rounded-lg border border-border bg-card px-2 py-2">
              {errorsLabel}
            </li>
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
