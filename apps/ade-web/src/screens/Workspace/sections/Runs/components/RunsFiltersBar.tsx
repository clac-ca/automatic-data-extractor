import { Button } from "@ui/Button";

import type { RunsCounts, RunsFilters } from "../types";
import { DATE_RANGE_OPTIONS, RUN_STATUS_META } from "../constants";

export function RunsFiltersBar({
  filters,
  configOptions,
  ownerOptions,
  resultEnabled,
  counts,
  showingCount,
  totalCount,
  onChange,
  onReset,
}: {
  filters: RunsFilters;
  configOptions: string[];
  ownerOptions: string[];
  resultEnabled: boolean;
  counts: RunsCounts;
  showingCount: number;
  totalCount: number;
  onChange: (next: Partial<RunsFilters>) => void;
  onReset: () => void;
}) {
  const activeChips = buildActiveFilterChips(filters);

  return (
    <div className="shrink-0 border-b border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1fr_1fr]">
          <select
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={filters.dateRange}
            onChange={(event) => onChange({ dateRange: event.target.value as RunsFilters["dateRange"] })}
          >
            {DATE_RANGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={filters.status}
            onChange={(event) => onChange({ status: event.target.value as RunsFilters["status"] })}
          >
            <option value="all">Status: all</option>
            <option value="succeeded">Success</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
            <option value="queued">Queued</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={filters.result}
            onChange={(event) => onChange({ result: event.target.value as RunsFilters["result"] })}
            disabled={!resultEnabled}
          >
            <option value="all">Result: all</option>
            <option value="clean">Clean</option>
            <option value="warnings">Warnings</option>
            <option value="errors">Errors</option>
          </select>
          <select
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={filters.config}
            onChange={(event) => onChange({ config: event.target.value })}
          >
            <option value="any">Config: any</option>
            {configOptions.map((config) => (
              <option key={config} value={config}>
                {config}
              </option>
            ))}
          </select>
          <select
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={filters.owner}
            onChange={(event) => onChange({ owner: event.target.value })}
            disabled={ownerOptions.length === 0}
          >
            <option value="all">Owner: all</option>
            {ownerOptions.map((owner) => (
              <option key={owner} value={owner}>
                {owner}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>
            Showing <span className="font-semibold text-foreground">{showingCount}</span> of{" "}
            <span className="font-semibold text-foreground">{totalCount}</span>
          </span>
          <Button size="sm" variant="ghost" onClick={onReset}>
            Reset
          </Button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <StatusChip
          label="All"
          count={counts.total}
          active={filters.status === "all"}
          onClick={() => onChange({ status: "all" })}
        />
        <StatusChip
          label={RUN_STATUS_META.queued.label}
          count={counts.queued}
          tone="muted"
          active={filters.status === "queued"}
          onClick={() => onChange({ status: "queued" })}
        />
        <StatusChip
          label={RUN_STATUS_META.running.label}
          count={counts.running}
          tone="info"
          active={filters.status === "running"}
          onClick={() => onChange({ status: "running" })}
        />
        <StatusChip
          label={RUN_STATUS_META.succeeded.label}
          count={counts.success}
          tone="success"
          active={filters.status === "succeeded"}
          onClick={() => onChange({ status: "succeeded" })}
        />
        <StatusChip
          label={RUN_STATUS_META.failed.label}
          count={counts.failed}
          tone="danger"
          active={filters.status === "failed"}
          onClick={() => onChange({ status: "failed" })}
        />
        <StatusChip
          label={RUN_STATUS_META.cancelled.label}
          count={counts.cancelled}
          tone="muted"
          active={filters.status === "cancelled"}
          onClick={() => onChange({ status: "cancelled" })}
        />
      </div>

      {activeChips.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">Active filters</span>
          {activeChips.map((chip) => (
            <span key={chip} className="rounded-full border border-border bg-background px-3 py-1 text-muted-foreground">
              {chip}
            </span>
          ))}
          <button
            type="button"
            onClick={onReset}
            className="rounded-full border border-border bg-muted/40 px-3 py-1 font-semibold text-muted-foreground hover:text-foreground"
          >
            Clear all
          </button>
        </div>
      ) : (
        <div className="mt-3 text-xs text-muted-foreground">No filters applied</div>
      )}
    </div>
  );
}

function StatusChip({
  label,
  count,
  active,
  tone = "default",
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  tone?: "default" | "success" | "danger" | "info" | "muted";
  onClick: () => void;
}) {
  const toneClass =
    tone === "success"
      ? "text-success-700"
      : tone === "danger"
        ? "text-danger-700"
        : tone === "info"
          ? "text-info-700"
          : "text-muted-foreground";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition ${
        active ? "border-transparent bg-brand-600 text-on-brand" : "border-border bg-background"
      }`}
    >
      <span className={active ? "text-on-brand" : toneClass}>{label}</span>
      <span className={active ? "text-on-brand/80" : "text-muted-foreground"}>{count}</span>
    </button>
  );
}

function buildActiveFilterChips(filters: RunsFilters) {
  const chips: string[] = [];
  if (filters.search) chips.push(`Search: ${filters.search}`);
  if (filters.status !== "all") chips.push(`Status: ${RUN_STATUS_META[filters.status].label}`);
  if (filters.result !== "all") {
    const resultLabel =
      filters.result === "clean" ? "Clean" : filters.result === "warnings" ? "Warnings" : "Errors";
    chips.push(`Result: ${resultLabel}`);
  }
  if (filters.config !== "any") chips.push(`Config: ${filters.config}`);
  if (filters.owner !== "all") chips.push(`Owner: ${filters.owner}`);
  if (filters.dateRange !== "14d") {
    const rangeLabel = DATE_RANGE_OPTIONS.find((option) => option.value === filters.dateRange)?.label ?? "Custom range";
    chips.push(rangeLabel);
  }
  return chips;
}
