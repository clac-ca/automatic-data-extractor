import clsx from "clsx";
import type { KeyboardEvent } from "react";

import { RUN_STATUS_META } from "../constants";
import { formatNumber, formatResultLabel } from "../utils";
import type { RunRecord } from "../types";

const INTERACTIVE_SELECTOR =
  "button, a, input, select, textarea, [role='button'], [role='menuitem'], [data-ignore-row-click='true']";

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest(INTERACTIVE_SELECTOR));
}

export function RunsTable({
  runs,
  totalCount,
  activeId,
  onSelect,
}: {
  runs: RunRecord[];
  totalCount: number;
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-3 text-xs text-muted-foreground">
        <span>Showing {formatNumber(runs.length)} of {formatNumber(totalCount)} runs</span>
        <span>Sorted by started time</span>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[960px]">
          <div className="grid grid-cols-[140px_1.4fr_170px_140px_110px_120px_110px_120px] border-b border-border bg-muted/40 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            <span>Status</span>
            <span>Input</span>
            <span>Config</span>
            <span>Started</span>
            <span>Duration</span>
            <span>Result</span>
            <span>Rows</span>
            <span>Owner</span>
          </div>
          <div role="list">
            {runs.map((run) => {
              const meta = RUN_STATUS_META[run.status];
              const isActive = activeId === run.id;

              const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                if (event.currentTarget !== event.target) return;
                event.preventDefault();
                onSelect(run.id);
              };

              return (
                <div key={run.id} className="border-b border-border/70">
                  <div
                    role="listitem"
                    tabIndex={0}
                    onKeyDown={onKeyDown}
                    onClick={(event) => {
                      if (isInteractiveTarget(event.target)) return;
                      onSelect(run.id);
                    }}
                    className={clsx(
                      "grid cursor-pointer grid-cols-[140px_1.4fr_170px_140px_110px_120px_110px_120px] items-center px-4 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      isActive ? "bg-brand-50 dark:bg-brand-500/20" : "hover:bg-muted/40",
                    )}
                  >
                    <span className="inline-flex items-center gap-2 text-xs font-semibold text-foreground">
                      <span className={clsx("h-2.5 w-2.5 rounded-full", meta.dotClass)} />
                      {meta.label}
                    </span>
                    <span>
                      <p className="font-semibold text-foreground">{run.inputName}</p>
                      <p className="text-[11px] text-muted-foreground">{run.id}</p>
                    </span>
                  <span className="text-xs text-foreground">{run.configLabel}</span>
                  <span className="text-xs text-muted-foreground">{run.startedAtLabel}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatResultLabel(run)}
                  </span>
                    <span className="text-sm text-muted-foreground">{run.durationLabel}</span>
                    <span className="text-xs text-muted-foreground">{formatResultLabel(run)}</span>
                    <span className="text-sm text-foreground">{formatNumber(run.rows)}</span>
                    <span className="text-sm text-foreground">{run.ownerLabel}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
