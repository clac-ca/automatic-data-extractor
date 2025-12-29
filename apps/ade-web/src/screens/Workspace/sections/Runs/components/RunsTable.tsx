import clsx from "clsx";
import type { KeyboardEvent } from "react";

import { RUN_STATUS_META } from "../constants";
import { formatNumber, formatResultLabel } from "../utils";
import type { RunRecord } from "../types";

import { RunPreviewPanel } from "./RunPreviewPanel";

const INTERACTIVE_SELECTOR =
  "button, a, input, select, textarea, [role='button'], [role='menuitem'], [data-ignore-row-click='true']";

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest(INTERACTIVE_SELECTOR));
}

export function RunsTable({
  runs,
  totalCount,
  expandedId,
  onActivate,
}: {
  runs: RunRecord[];
  totalCount: number;
  expandedId: string | null;
  onActivate: (id: string) => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-3 text-xs text-muted-foreground">
        <span>Showing {formatNumber(runs.length)} of {formatNumber(totalCount)} runs</span>
        <span>Sorted by started time</span>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[1060px]">
          <div className="grid grid-cols-[140px_1.3fr_170px_130px_120px_110px_110px_120px_120px] border-b border-border bg-muted/40 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            <span>Status</span>
            <span>Input</span>
            <span>Config</span>
            <span>Started</span>
            <span>Result</span>
            <span>Rows</span>
            <span>Duration</span>
            <span>Owner</span>
            <span>Actions</span>
          </div>
          <div role="list">
            {runs.map((run) => {
              const meta = RUN_STATUS_META[run.status];
              const isExpanded = expandedId === run.id;
              const previewId = `runs-preview-${run.id}`;

              const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                if (event.currentTarget !== event.target) return;
                event.preventDefault();
                onActivate(run.id);
              };

              return (
                <div key={run.id} className="border-b border-border/70">
                  <div
                    role="listitem"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    aria-controls={isExpanded ? previewId : undefined}
                    onKeyDown={onKeyDown}
                    onClick={(event) => {
                      if (isInteractiveTarget(event.target)) return;
                      onActivate(run.id);
                    }}
                    className={clsx(
                      "grid cursor-pointer grid-cols-[140px_1.3fr_170px_130px_120px_110px_110px_120px_120px] items-center px-4 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      isExpanded ? "bg-brand-50 dark:bg-brand-500/20" : "hover:bg-muted/40",
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
                  <span className="text-sm text-foreground">{formatNumber(run.rows)}</span>
                  <span className="text-sm text-muted-foreground">{run.durationLabel}</span>
                  <span className="text-sm text-foreground">{run.ownerLabel}</span>
                    <span className="text-xs text-muted-foreground">Logs · Output</span>
                  </div>

                  {isExpanded ? (
                    <div id={previewId} className="bg-background px-4 pb-4 pt-2">
                      <RunPreviewPanel run={run} onClose={() => onActivate(run.id)} />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
