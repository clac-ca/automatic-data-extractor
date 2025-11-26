import type { ArtifactV1 } from "@schema";
import type { AdeEvent } from "@shared/runs/types";

export function ArtifactSummary({ artifact }: { artifact: ArtifactV1 }) {
  if (!artifact.tables.length) {
    return <p className="text-xs text-slate-500">No tables recorded in the artifact.</p>;
  }

  return (
    <div className="space-y-3">
      {artifact.tables.map((table) => (
        <div
          key={`${table.source_file}-${table.source_sheet ?? ""}-${table.table_index}`}
          className="rounded-md border border-slate-200 bg-white px-3 py-2"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold text-slate-800">
              {table.source_file}
              {table.source_sheet ? ` — ${table.source_sheet}` : ""}
              {table.table_index > 1 ? ` (table ${table.table_index})` : ""}
            </p>
            <p className="text-[11px] text-slate-500">
              Header row {table.header.row_index}, {table.header.cells.length} columns
            </p>
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-3">
            <div className="rounded border border-emerald-100 bg-emerald-50 px-2 py-1">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-600">Mapped columns</p>
              {table.mapped_columns.length ? (
                <ul className="mt-1 space-y-0.5 text-xs text-emerald-700">
                  {table.mapped_columns.map((column) => (
                    <li key={`${column.field}-${column.source_column_index}`} className="flex items-center gap-1">
                      <span className="rounded bg-white px-1 py-0.5 text-[10px] font-semibold text-emerald-700">
                        {column.field}
                      </span>
                      <span className="truncate">→ {column.header}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-emerald-700">None mapped</p>
              )}
            </div>
            <div className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Unmapped columns</p>
              {table.unmapped_columns.length ? (
                <ul className="mt-1 space-y-0.5 text-xs text-slate-700">
                  {table.unmapped_columns.map((column) => (
                    <li key={`${column.output_header}-${column.source_column_index}`} className="flex items-center gap-1">
                      <span className="rounded bg-white px-1 py-0.5 text-[10px] font-semibold text-slate-700">
                        {column.output_header}
                      </span>
                      <span className="truncate">from column {column.source_column_index}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-slate-600">No unmapped columns</p>
              )}
            </div>
            <div className="rounded border border-amber-100 bg-amber-50 px-2 py-1">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Validation issues</p>
              {table.validation_issues.length ? (
                <ul className="mt-1 space-y-0.5 text-xs text-amber-800">
                  {table.validation_issues.slice(0, 4).map((issue, index) => (
                    <li key={`${issue.field}-${issue.row_index}-${index}`} className="flex flex-wrap items-center gap-1">
                      <span className="rounded bg-white px-1 py-0.5 text-[10px] font-semibold text-amber-700">
                        {issue.severity}
                      </span>
                      <span className="truncate">
                        Row {issue.row_index}, {issue.field}: {issue.code}
                      </span>
                    </li>
                  ))}
                  {table.validation_issues.length > 4 ? (
                    <li className="text-[11px] text-amber-700">
                      +{table.validation_issues.length - 4} more validation issues
                    </li>
                  ) : null}
                </ul>
              ) : (
                <p className="text-[11px] text-amber-700">No validation issues</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function TelemetrySummary({ events }: { events: AdeEvent[] }) {
  if (!events.length) {
    return <p className="text-xs text-slate-500">No telemetry events captured.</p>;
  }

  const levelCounts = events.reduce<Record<string, number>>((acc, event) => {
    const level = (event.run?.level as string | undefined) ?? (event.log?.level as string | undefined) ?? "info";
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
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">{event.type}</span>
              <span className="text-[11px] text-slate-500">{formatTimestamp(event.created_at)}</span>
            </div>
            <p className="text-[11px] text-slate-600">Level: {levelFor(event)}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatTimestamp(timestamp: string | number): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleString();
}

function levelFor(event: AdeEvent): string {
  return (event.run?.level as string | undefined) ?? (event.log?.level as string | undefined) ?? "info";
}
