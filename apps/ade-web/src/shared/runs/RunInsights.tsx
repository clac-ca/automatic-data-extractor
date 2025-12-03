import type { RunSummaryV1 } from "@schema";
import type { AdeEvent } from "@shared/runs/types";

export function RunSummaryView({ summary }: { summary: RunSummaryV1 }) {
  const totalIssues = summary.core.validation_issue_count_total;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Tables" value={summary.core.table_count} />
        <Metric label="Rows" value={summary.core.row_count ?? "—"} />
        <Metric label="Mapped fields" value={summary.core.mapped_field_count} />
        <Metric label="Issues" value={totalIssues} intent={totalIssues > 0 ? "warn" : "ok"} />
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded border border-slate-200 bg-white px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Files</p>
          {summary.breakdowns.by_file.length === 0 ? (
            <p className="text-xs text-slate-500">No files recorded.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-xs text-slate-700">
              {summary.breakdowns.by_file.map((file) => (
                <li key={file.source_file} className="flex items-center justify-between gap-3">
                  <span className="truncate font-semibold text-slate-800">{file.source_file}</span>
                  <span className="text-[11px] text-slate-500">
                    {file.table_count} tables · {file.row_count ?? "?"} rows · {file.validation_issue_count_total} issues
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded border border-slate-200 bg-white px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Fields</p>
          {summary.breakdowns.by_field.length === 0 ? (
            <p className="text-xs text-slate-500">No field mappings recorded.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-xs text-slate-700">
              {summary.breakdowns.by_field.slice(0, 6).map((field) => (
                <li key={field.field} className="flex items-center justify-between gap-3">
                  <span className="truncate font-semibold text-slate-800">
                    {field.label || field.field} {field.required ? "• required" : ""}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {field.mapped ? "mapped" : "unmapped"} · {field.validation_issue_count_total} issues
                  </span>
                </li>
              ))}
              {summary.breakdowns.by_field.length > 6 ? (
                <li className="text-[11px] text-slate-500">
                  +{summary.breakdowns.by_field.length - 6} more fields
                </li>
              ) : null}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export function TelemetrySummary({ events }: { events: AdeEvent[] }) {
  if (!events.length) {
    return <p className="text-xs text-slate-500">No telemetry events captured.</p>;
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
      <div className="flex flex-wrap gap-2 text-[11px] text-slate-600">
        {Object.entries(levelCounts).map(([level, count]) => (
          <span
            key={level}
            className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700"
          >
            {level}: {count}
          </span>
        ))}
      </div>
      <ul className="space-y-1">
        {recentEvents.map((event) => (
          <li
            key={`${event.created_at}-${event.type}`}
            className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-800"
          >
            {(() => {
              const payload = payloadOf(event);
              const message = (payload.message as string | undefined)?.trim();
              return (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">{event.type}</span>
                    <span className="text-[11px] text-slate-500">{formatTimestamp(event.created_at)}</span>
                  </div>
                  <p className="text-[11px] text-slate-600">
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

function levelFor(event: AdeEvent): string {
  const payload = payloadOf(event);
  const streamLevel = (payload.stream as string | undefined) === "stderr" ? "warning" : undefined;
  return (payload.level as string | undefined) ?? streamLevel ?? "info";
}

function payloadOf(event: AdeEvent): Record<string, unknown> {
  const payload = event.payload;
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
    intent === "warn" ? "text-amber-700" : intent === "ok" ? "text-emerald-700" : "text-slate-700";
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`text-sm font-semibold ${color}`}>{value}</p>
    </div>
  );
}
