import type { RunSummary } from "@schema";
import type { RunStreamEvent } from "@shared/runs/types";

export function RunSummaryView({ summary }: { summary: Partial<RunSummary> }) {
  const counts = summary.counts;
  const totalIssues = summary.validation?.issues_total;
  const fields = summary.fields ?? [];
  const columns = summary.columns ?? [];
  const topFields = fields.slice(0, 6);
  const topColumns = columns.slice(0, 5);
  const issuesIntent = typeof totalIssues === "number" ? (totalIssues > 0 ? "warn" : "ok") : "default";
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Tables" value={counts?.tables?.total ?? "—"} />
        <Metric label="Rows" value={counts?.rows?.total ?? "—"} />
        <Metric label="Mapped fields" value={counts?.fields?.mapped ?? "—"} />
        <Metric label="Issues" value={totalIssues ?? "—"} intent={issuesIntent} />
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded border border-border bg-card px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Fields</p>
          {fields.length === 0 ? <p className="text-xs text-muted-foreground">No field mappings recorded.</p> : (
            <ul className="mt-2 space-y-1 text-xs text-foreground">
              {topFields.map((field) => (
                <li key={field.field} className="flex items-center justify-between gap-3">
                  <span className="truncate font-semibold text-foreground">
                    {field.label || field.field} {field.required ? "• required" : ""}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {field.mapped ? "mapped" : "unmapped"}
                    {typeof field.tables_mapped === "number" ? ` · ${field.tables_mapped} tables` : ""}
                  </span>
                </li>
              ))}
              {fields.length > topFields.length ? (
                <li className="text-[11px] text-muted-foreground">
                  +{fields.length - topFields.length} more fields
                </li>
              ) : null}
            </ul>
          )}
        </div>
        <div className="rounded border border-border bg-card px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Columns</p>
          {columns.length === 0 ? (
            <p className="text-xs text-muted-foreground">No column details recorded.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-xs text-foreground">
              {topColumns.map((column) => (
                <li key={column.header_normalized} className="flex items-center justify-between gap-3">
                  <span className="truncate font-semibold text-foreground">{column.header}</span>
                  <span className="text-[11px] text-muted-foreground">
                    {column.mapped ? "mapped" : "unmapped"} · {column.occurrences?.tables_seen ?? "—"} tables
                  </span>
                </li>
              ))}
              {columns.length > topColumns.length ? (
                <li className="text-[11px] text-muted-foreground">
                  +{columns.length - topColumns.length} more headers
                </li>
              ) : null}
            </ul>
          )}
          <div className="mt-2 text-[11px] text-muted-foreground">
            Distinct headers mapped: {counts?.columns?.distinct_headers_mapped ?? "—"} /{" "}
            {counts?.columns?.distinct_headers ?? "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

export function TelemetrySummary({ events }: { events: RunStreamEvent[] }) {
  if (!events.length) {
    return <p className="text-xs text-muted-foreground">No telemetry events captured.</p>;
  }

  const levelCounts = events.reduce<Record<string, number>>((acc, event) => {
    const payload = payloadOf(event);
    const streamLevel = (payload.stream as string | undefined) === "stderr" ? "warning" : undefined;
    const level = (payload.level as string | undefined) ?? streamLevel ?? "info";
    acc[level] = (acc[level] ?? 0) + 1;
    return acc;
  }, {});
  const recentEvents = events.slice(-6).reverse();

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
        {Object.entries(levelCounts).map(([level, count]) => (
          <span
            key={level}
            className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 font-semibold text-foreground"
          >
            {level}: {count}
          </span>
        ))}
      </div>
      <ul className="space-y-1">
        {recentEvents.map((event) => (
          <li
            key={`${event.timestamp}-${event.event}`}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
          >
            {(() => {
              const message = typeof event.message === "string" ? event.message.trim() : undefined;
              return (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">{event.event}</span>
                    <span className="text-[11px] text-muted-foreground">
                      {formatTimestamp(event.timestamp ?? event.created_at ?? "unknown")}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {message ? message : `Level: ${levelFor(event)}`}
                  </p>
                </>
              );
            })()}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatTimestamp(timestamp: string | number | Date): string {
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return String(timestamp);
  return date.toLocaleString();
}

function levelFor(event: RunStreamEvent): string {
  const payload = payloadOf(event);
  const streamLevel = (payload.stream as string | undefined) === "stderr" ? "warning" : undefined;
  return (payload.level as string | undefined) ?? streamLevel ?? "info";
}

function payloadOf(event: RunStreamEvent): Record<string, unknown> {
  const payload = event.data;
  if (payload && typeof payload === "object") {
    return payload as Record<string, unknown>;
  }
  return {};
}

function Metric({
  label,
  value,
  intent = "default",
}: {
  label: string;
  value: string | number;
  intent?: "default" | "warn" | "ok";
}) {
  const color =
    intent === "warn" ? "text-amber-700" : intent === "ok" ? "text-emerald-700" : "text-foreground";
  return (
    <div className="rounded border border-border bg-background px-2 py-1">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`text-sm font-semibold ${color}`}>{value}</p>
    </div>
  );
}
