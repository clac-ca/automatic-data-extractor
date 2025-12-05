import clsx from "clsx";

import type { PhaseState, RunStreamStatus } from "../state/runStream";
import type { WorkbenchRunSummary } from "../types";
import { RunSummaryView, TelemetrySummary } from "@shared/runs/RunInsights";

interface RunSummaryTabProps {
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly buildPhases: Record<string, PhaseState>;
  readonly runPhases: Record<string, PhaseState>;
  readonly runStatus?: RunStreamStatus;
  readonly runMode?: "validation" | "extraction";
}

export function RunSummaryTab({ latestRun, buildPhases, runPhases, runStatus, runMode }: RunSummaryTabProps) {
  if (!latestRun) {
    return (
      <div className="flex flex-1 items-center justify-center text-xs text-slate-500">
        No run yet. Run a test or validation to see details here.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto">
      <RunTimelineCard buildPhases={buildPhases} runPhases={runPhases} runStatus={runStatus} runMode={runMode} />
      <RunSummaryHeader summary={latestRun} />
      <RunOutputsCard summary={latestRun} />
      <RunCoreSummaryCard summary={latestRun} />
      <TelemetrySummaryCard summary={latestRun} />
    </div>
  );
}

function RunTimelineCard({
  buildPhases,
  runPhases,
  runStatus,
  runMode,
}: {
  readonly buildPhases: Record<string, PhaseState>;
  readonly runPhases: Record<string, PhaseState>;
  readonly runStatus?: RunStreamStatus;
  readonly runMode?: "validation" | "extraction";
}) {
  const buildEntries = Object.entries(buildPhases);
  const runEntries = Object.entries(runPhases);
  const hasAny = buildEntries.length > 0 || runEntries.length > 0 || runStatus;

  if (!hasAny) {
    return null;
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">Run timeline</p>
          <p className="text-[12px] text-slate-500">
            {runMode ? runMode === "validation" ? "Validation" : "Test run" : "Run"} · {runStatus ?? "idle"}
          </p>
        </div>
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <PhaseList title="Build" entries={buildEntries} fallback={buildFallback(runStatus)} />
        <PhaseList title="Run" entries={runEntries} fallback={runFallback(runStatus)} />
      </div>
    </section>
  );
}

function PhaseList({
  title,
  entries,
  fallback,
}: {
  readonly title: string;
  readonly entries: Array<[string, PhaseState]>;
  readonly fallback?: string;
}) {
  return (
    <div className="space-y-2">
      <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      {entries.length === 0 ? (
        <p className="text-[12px] text-slate-500">{fallback ?? "Waiting for updates…"}</p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map(([id, state]) => (
            <li key={id} className="flex items-start gap-2 rounded border border-slate-100 px-2 py-1">
              <span className={clsx("mt-[3px] inline-flex h-2 w-2 rounded-full", phaseTone(state.status))} aria-hidden />
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-slate-700">{prettyPhaseLabel(id)}</p>
                <p className="text-[12px] text-slate-500">
                  {state.message ?? phaseStatusLabel(state.status)}
                  {state.durationMs != null ? ` · ${formatRunDuration(state.durationMs)}` : ""}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
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
  const outputLabel =
    summary.outputFilename ||
    summary.outputPath?.split("/").pop() ||
    (summary.processedFile ? `${summary.processedFile.split("/").pop() ?? summary.processedFile}-normalized.xlsx` : "normalized.xlsx");
  const outputReady = summary.outputReady ?? true;

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-slate-500">Output file</p>
        {!summary.outputLoaded ? <span className="text-[12px] text-slate-400">Loading…</span> : null}
      </div>
      {summary.error ? (
        <p className="mt-2 text-sm text-rose-600">{summary.error}</p>
      ) : !summary.outputLoaded ? (
        <p className="mt-2 text-sm text-slate-500">Loading output…</p>
      ) : !outputReady ? (
        <p className="mt-2 text-sm text-slate-500">Output is not available yet.</p>
      ) : summary.outputUrl ? (
        <div className="mt-2 flex items-center justify-between rounded border border-slate-100 px-2 py-1 text-sm text-slate-800">
          <a href={summary.outputUrl} className="text-brand-600 hover:underline">
            {outputLabel}
          </a>
          {summary.outputPath ? (
            <span className="text-[11px] text-slate-500">{summary.outputPath}</span>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No output file was generated.</p>
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
  const cancelled = isCancelledStatus(status);
  const tone =
    status === "succeeded"
      ? "bg-emerald-500"
      : status === "running" || status === "queued"
        ? "bg-amber-400"
        : cancelled
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
  if (isCancelledStatus(status)) {
    return "Canceled";
  }
  switch (status) {
    case "succeeded":
      return "Succeeded";
    case "failed":
      return "Failed";
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

function phaseTone(status: PhaseState["status"]) {
  switch (status) {
    case "succeeded":
      return "bg-emerald-500";
    case "running":
      return "bg-amber-400";
    case "failed":
      return "bg-rose-500";
    case "skipped":
      return "bg-slate-400";
    default:
      return "bg-slate-300";
  }
}

function phaseStatusLabel(status: PhaseState["status"]) {
  switch (status) {
    case "succeeded":
      return "Completed";
    case "running":
      return "In progress";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
    default:
      return "Pending";
  }
}

function isCancelledStatus(status: WorkbenchRunSummary["status"]) {
  return status === "cancelled";
}

function prettyPhaseLabel(id: string) {
  return id
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

function buildFallback(status?: RunStreamStatus) {
  if (status === "waiting_for_build") return "Waiting for build queue…";
  if (status === "queued") return "Queued…";
  if (status === "building") return "Building environment…";
  return "No build phases reported.";
}

function runFallback(status?: RunStreamStatus) {
  if (status === "running") return "Running…";
  if (status === "queued" || status === "waiting_for_build" || status === "building") return "Run pending.";
  return "No run phases reported.";
}
