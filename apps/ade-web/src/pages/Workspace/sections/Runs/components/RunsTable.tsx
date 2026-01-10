import clsx from "clsx";

import { LogsIcon, OutputIcon } from "@components/icons";
import { useEffect, useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";

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
  activeId,
  onSelect,
  onNavigate,
  expandedId,
  expandedContent,
}: {
  runs: RunRecord[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNavigate?: (id: string) => void;
  expandedId?: string | null;
  expandedContent?: ReactNode;
}) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    if (!activeId) return;
    const container = listRef.current;
    const row = rowRefs.current.get(activeId);
    if (!container || !row) return;
    const nextTop = row.offsetTop - container.offsetTop;
    container.scrollTo({ top: Math.max(0, nextTop) });
  }, [activeId]);

  const handleKeyNavigate = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!onNavigate) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest("input, textarea, select, button, a, [role='button'], [role='menuitem']")) {
      return;
    }
    if (runs.length === 0) return;
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

    event.preventDefault();
    const currentIndex = runs.findIndex((run) => run.id === activeId);
    if (currentIndex < 0) {
      onNavigate(runs[0].id);
      return;
    }
    const nextIndex =
      event.key === "ArrowDown" ? Math.min(runs.length - 1, currentIndex + 1) : Math.max(0, currentIndex - 1);
    onNavigate(runs[nextIndex].id);
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-card">
      <div className="shrink-0 border-b border-border bg-background/40 px-6 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        <div className="grid grid-cols-[120px_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.8fr)_minmax(0,0.6fr)_minmax(0,0.8fr)_minmax(0,0.6fr)] items-center gap-3">
          <div>Status</div>
          <div>Input</div>
          <div>Config</div>
          <div>Started</div>
          <div className="text-right">Duration</div>
          <div className="text-right">Result</div>
          <div className="text-right">Rows</div>
          <div>Owner</div>
          <div className="text-right">Actions</div>
        </div>
      </div>

      <div
        ref={listRef}
        className="flex-1 min-h-0 overflow-y-auto px-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        tabIndex={0}
        role="listbox"
        aria-label="Runs"
        onKeyDown={handleKeyNavigate}
      >
        <div className="flex flex-col">
          {runs.map((run) => {
            const meta = RUN_STATUS_META[run.status];
            const isActive = activeId === run.id;
            const isExpanded = Boolean(expandedContent && expandedId === run.id);
            const previewId = `runs-preview-${run.id}`;

            const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              if (event.currentTarget !== event.target) return;
              event.preventDefault();
              onSelect(run.id);
            };

            return (
              <div
                key={run.id}
                ref={(node) => {
                  if (node) rowRefs.current.set(run.id, node);
                  else rowRefs.current.delete(run.id);
                }}
                className="border-b border-border/70"
              >
                <div
                  role="option"
                  tabIndex={0}
                  onKeyDown={onKeyDown}
                  onClick={(event) => {
                    if (isInteractiveTarget(event.target)) return;
                    onSelect(run.id);
                  }}
                  className={clsx(
                    "grid cursor-pointer grid-cols-[120px_minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.8fr)_minmax(0,0.6fr)_minmax(0,0.8fr)_minmax(0,0.6fr)] items-center gap-3 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                    isActive ? "bg-muted" : "hover:bg-background dark:hover:bg-muted/40",
                  )}
                  aria-selected={isActive}
                  aria-expanded={isExpanded}
                  aria-controls={isExpanded ? previewId : undefined}
                >
                  <div className="inline-flex items-center gap-2 text-xs font-semibold text-foreground">
                    <span className={clsx("h-2.5 w-2.5 rounded-full", meta.dotClass)} />
                    {meta.label}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-foreground">{run.inputName}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{run.id}</p>
                  </div>
                  <span className="truncate text-xs text-foreground">{run.configLabel}</span>
                  <span className="text-xs text-muted-foreground">{run.startedAtLabel}</span>
                  <span className="text-right text-sm text-muted-foreground">{run.durationLabel}</span>
                  <div className="flex justify-end">
                    <ResultBadge run={run} />
                  </div>
                  <span className="text-right text-sm text-foreground">{formatNumber(run.rows)}</span>
                  <span className="truncate text-sm text-foreground">{run.ownerLabel}</span>
                  <div className="flex items-center justify-end gap-2" data-ignore-row-click>
                    <ActionButton
                      label="View logs"
                      href={run.raw.links?.logs ?? null}
                      icon={<LogsIcon className="h-4 w-4" />}
                    />
                    <ActionButton
                      label={run.raw.output?.ready ? "Open output" : "Output not ready"}
                      href={run.raw.output?.ready ? (run.raw.links?.output_download ?? run.raw.links?.output ?? null) : null}
                      icon={<OutputIcon className="h-4 w-4" />}
                    />
                  </div>
                </div>

                {isExpanded ? (
                  <div
                    id={previewId}
                    role="region"
                    aria-label={`Run details for ${run.inputName}`}
                    className="bg-background/60 px-6 pb-4 pt-2"
                  >
                    <div className="rounded-2xl border border-border bg-card shadow-sm">{expandedContent}</div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ResultBadge({ run }: { run: RunRecord }) {
  const label = formatResultLabel(run);
  const isUnknown = label === "—";
  const isClean = label === "Clean";
  const toneClass =
    typeof run.errors === "number" && run.errors > 0
      ? "bg-destructive/10 text-destructive dark:bg-destructive/20"
      : typeof run.warnings === "number" && run.warnings > 0
        ? "bg-accent text-accent-foreground"
        : isClean
          ? "bg-primary/10 text-primary"
          : "bg-muted text-muted-foreground";

  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center rounded-full px-2 py-1 text-[11px] font-semibold",
        toneClass,
        isUnknown ? "opacity-70" : "",
      )}
    >
      {label}
    </span>
  );
}

function ActionButton({
  label,
  href,
  icon,
}: {
  label: string;
  href: string | null;
  icon: ReactNode;
}) {
  if (href) {
    return (
      <a
        href={href}
        onClick={(event) => event.stopPropagation()}
        target="_blank"
        rel="noreferrer"
        aria-label={label}
        title={label}
        className={clsx(
          "inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition",
          "hover:bg-background hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
      >
        {icon}
      </a>
    );
  }

  return (
    <button
      type="button"
      onClick={(event) => event.stopPropagation()}
      disabled
      aria-label={label}
      title={label}
      className={clsx(
        "inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground/60",
        "cursor-not-allowed",
      )}
    >
      {icon}
    </button>
  );
}
