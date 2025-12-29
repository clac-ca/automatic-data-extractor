import { Input } from "@ui/Input";
import { Button } from "@ui/Button";

import type { RunsFilters } from "../types";
import { DATE_RANGE_OPTIONS } from "../constants";

export function RunsFiltersBar({
  filters,
  configOptions,
  ownerOptions,
  resultEnabled,
  onChange,
  onReset,
}: {
  filters: RunsFilters;
  configOptions: string[];
  ownerOptions: string[];
  resultEnabled: boolean;
  onChange: (next: Partial<RunsFilters>) => void;
  onReset: () => void;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="grid gap-3 lg:grid-cols-[1.6fr_1fr_1fr_1fr_1fr_1fr_auto]">
        <Input
          placeholder="Search inputs, owners, configs"
          value={filters.search}
          onChange={(event) => onChange({ search: event.target.value })}
        />
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
        <Button size="sm" variant="ghost" onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}
