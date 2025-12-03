import clsx from "clsx";

import type { WorkbenchRunSummary } from "../types";
import { RunSummaryView, TelemetrySummary } from "@shared/runs/RunInsights";

export function RunSummaryTab({ latestRun }: { readonly latestRun?: WorkbenchRunSummary | null }) {
  if (!latestRun) {
    return (
      <div className="flex flex-1 items-center justify-center text-xs text-slate-500">
        No run yet. Run a test or validation to see details here.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto">
      <RunSummaryHeader summary={latestRun} />
      <RunOutputsCard summary={latestRun} />
      <RunCoreSummaryCard summary={latestRun} />
      <TelemetrySummaryCard summary={latestRun} />
    </div>
  );
}

function RunSummaryHeader({ summary }: { readonly summary: WorkbenchRunSummary }) {
  const durationLabel = summary.durationMs != null ? formatRunDuration(summary.durationMs) : null;
  const sheetLabel =
    summary.sheetNames && summary.sheetNames.length > 0
      ? summary.sheetNames.join(", ")
      : summary.sheetNames
        ? "All worksheets"
        : null;

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
          <StatusDot status={summary.status} />
          <span className="font-semibold text-slate-700">Run</span>
          <span className="text-slate-400" title={summary.runId}>
            #{summary.runId}
          </span>
        </div>
        <div className="text-sm font-semibold text-slate-800">
          {statusLabel(summary.status)}
          {durationLabel ? <span className="font-normal text-slate-500"> · {durationLabel}</span> : null}
        </div>
        <div className="text-xs text-slate-500">
          {summary.documentName ?? "Document not recorded"}
          {sheetLabel ? ` · ${sheetLabel}` : null}
        </div>
        {summary.completedAt ? (
          <div className="text-[11px] text-slate-400">
            Completed {formatRelative(summary.completedAt)}
          </div>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {summary.logsUrl ? (
          <a
            href={summary.logsUrl}
            className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] font-semibold text-slate-700 shadow-sm hover:border-slate-300 hover:bg-white"
          >
            Download logs
          </a>
        ) : null}
      </div>
    </div>
  );
}

function RunOutputsCard({ summary }: { readonly summary: WorkbenchRunSummary }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">Output files</p>
        {!summary.outputsLoaded ? (
          <span className="text-[12px] text-slate-400">Loading…</span>
        ) : null}
      </div>
      {summary.error ? (
        <p className="mt-2 text-sm text-rose-600">{summary.error}</p>
      ) : !summary.outputsLoaded ? (
        <p className="mt-2 text-sm text-slate-500">Loading outputs…</p>
      ) : summary.outputs.length > 0 ? (
        <ul className="mt-2 space-y-1 text-sm text-slate-800">
          {summary.outputs.map((file) => {
            const encodedPath =
              file.path?.split("/").map(encodeURIComponent).join("/") ??
              file.name.split("/").map(encodeURIComponent).join("/");
            const href = file.download_url
              ? file.download_url
              : summary.outputsBase
                ? `${summary.outputsBase}/${encodedPath}`
                : undefined;
            const content = (
              <span className="text-brand-600">
                {file.name || file.path}
              </span>
            );
            return (
              <li
                key={file.path ?? file.name}
                className="flex items-center justify-between gap-2 break-all rounded border border-slate-100 px-2 py-1"
              >
                {href ? (
                  <a href={href} className="text-brand-600 hover:underline">
                    {file.name || file.path}
                  </a>
                ) : (
                  content
                )}
                <span className="text-[11px] text-slate-500">{file.byte_size.toLocaleString()} bytes</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No output files were generated.</p>
      )}
    </section>
  );
}

function RunCoreSummaryCard({ summary }: { readonly summary: WorkbenchRunSummary }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">Run summary</p>
      {summary.summaryError ? (
        <p className="mt-2 text-sm text-rose-600">{summary.summaryError}</p>
      ) : !summary.summaryLoaded ? (
        <p className="mt-2 text-sm text-slate-500">Loading summary…</p>
      ) : summary.summary ? (
        <div className="mt-2">
          <RunSummaryView summary={summary.summary} />
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Summary not available.</p>
      )}
    </section>
  );
}

function TelemetrySummaryCard({ summary }: { readonly summary: WorkbenchRunSummary }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">Telemetry summary</p>
      {summary.telemetryError ? (
        <p className="mt-2 text-sm text-rose-600">{summary.telemetryError}</p>
      ) : !summary.telemetryLoaded ? (
        <p className="mt-2 text-sm text-slate-500">Loading telemetry…</p>
      ) : summary.telemetry && summary.telemetry.length > 0 ? (
        <div className="mt-2">
          <TelemetrySummary events={[...summary.telemetry]} />
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No telemetry events captured.</p>
      )}
    </section>
  );
}

function StatusDot({ status }: { readonly status: WorkbenchRunSummary["status"] }) {
  const tone =
    status === "succeeded"
      ? "bg-emerald-500"
      : status === "running" || status === "queued"
        ? "bg-amber-400"
        : status === "canceled"
          ? "bg-slate-400"
          : "bg-rose-500";

  return <span className={clsx("inline-block h-2.5 w-2.5 rounded-full", tone)} aria-hidden />;
}

function formatRunDuration(valueMs: number): string {
  if (!Number.isFinite(valueMs) || valueMs < 0) {
    return "";
  }
  if (valueMs < 1000) {
    return `${Math.round(valueMs)} ms`;
  }
  if (valueMs < 60_000) {
    return `${(valueMs / 1000).toFixed(1)} s`;
  }
  const minutes = Math.floor(valueMs / 60_000);
  const seconds = Math.round((valueMs % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

function statusLabel(status: WorkbenchRunSummary["status"]): string {
  switch (status) {
    case "succeeded":
      return "Succeeded";
    case "failed":
      return "Failed";
    case "canceled":
      return "Canceled";
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    default:
      return status;
  }
}

function formatRelative(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}
