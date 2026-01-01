import { Button } from "@/components/ui/button";

import type { RunConfigOption, RunsFilters } from "../types";
import { DATE_RANGE_OPTIONS } from "../constants";

export function RunsFiltersBar({
  filters,
  configOptions,
  showingCount,
  totalCount,
  onChange,
  onReset,
}: {
  filters: RunsFilters;
  configOptions: RunConfigOption[];
  showingCount: number;
  totalCount: number;
  onChange: (next: Partial<RunsFilters>) => void;
  onReset: () => void;
}) {
  return (
    <div className="shrink-0 border-b border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr]">
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
            value={filters.configurationId ?? ""}
            onChange={(event) => onChange({ configurationId: event.target.value || null })}
          >
            <option value="">Config: all</option>
            {configOptions.map((config) => (
              <option key={config.id} value={config.id}>
                {config.label}
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
    </div>
  );
}
