import { useEffect, useMemo, useRef, useState } from "react";
import type { ConfigBuilderPane } from "@app/nav/urlState";
import type { RunSummaryV1 } from "@schema";
import type { AdeEvent, RunStatus } from "@shared/runs/types";
import clsx from "clsx";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchConsoleLine, WorkbenchValidationState } from "../types";
import { RunSummaryView, TelemetrySummary } from "@shared/runs/RunInsights";

export interface WorkbenchRunSummary {
  readonly runId: string;
  readonly status: RunStatus;
  readonly downloadBase: string;
  readonly outputs: ReadonlyArray<{
    name: string;
    path?: string;
    byte_size: number;
    download_url?: string | null;
  }>;
  readonly outputsLoaded: boolean;
  readonly summary?: RunSummaryV1 | null;
  readonly summaryLoaded: boolean;
  readonly summaryError?: string | null;
  readonly telemetry?: readonly AdeEvent[] | null;
  readonly telemetryLoaded: boolean;
  readonly telemetryError?: string | null;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
  readonly error?: string | null;
  readonly startedAt?: string | null;
  readonly completedAt?: string | null;
  readonly durationMs?: number | null;
}

interface BottomPanelProps {
  readonly height: number;
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly validation: WorkbenchValidationState;
  readonly activePane: ConfigBuilderPane;
  readonly onPaneChange: (pane: ConfigBuilderPane) => void;
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly onShowRunDetails?: () => void;
  readonly onClearConsole?: () => void;
}

export function BottomPanel({
  height,
  consoleLines,
  validation,
  activePane,
  onPaneChange,
  latestRun,
  onShowRunDetails,
  onClearConsole,
}: BottomPanelProps) {
  const [originFilter, setOriginFilter] = useState<"all" | "run" | "build" | "raw">("all");
  const [levelFilter, setLevelFilter] = useState<"all" | "info" | "warning" | "error" | "success">("all");
  const [followLogs, setFollowLogs] = useState(true);

  const filteredConsoleLines = useMemo(() => {
    const filterSeverity = resolveSeverity(levelFilter);
    return consoleLines.filter((line) => {
      const originMatches = originFilter === "all" || (line.origin ?? "run") === originFilter;
      const severity = resolveSeverity(line.level);
      const levelMatches = levelFilter === "all" || severity >= filterSeverity;
      return originMatches && levelMatches;
    });
  }, [consoleLines, originFilter, levelFilter]);
  const hasConsoleLines = filteredConsoleLines.length > 0;
  const hasAnyConsoleLines = consoleLines.length > 0;
  const hasProblems = validation.messages.length > 0;
  const hasRun = Boolean(latestRun);

  return (
    <section
      className="flex min-h-0 flex-col overflow-hidden border-t border-slate-200 bg-slate-50"
      style={{ height }}
    >
      <TabsRoot
        value={activePane}
        onValueChange={(value) => onPaneChange(value as ConfigBuilderPane)}
      >
        <div className="flex flex-none items-center justify-between border-b border-slate-200 px-3 py-1.5">
          <TabsList className="flex items-center gap-3 text-[11px] font-medium">
            <TabsTrigger
              value="terminal"
              className="rounded px-2 py-1 uppercase tracking-[0.16em]"
            >
              Terminal
            </TabsTrigger>
            <TabsTrigger
              value="runSummary"
              className="rounded px-2 py-1 uppercase tracking-[0.16em]"
            >
              Run
              {hasRun ? (
                <span className="ml-1 text-[10px] lowercase text-slate-500">
                  {latestRun?.status}
                </span>
              ) : null}
            </TabsTrigger>
            <TabsTrigger
              value="problems"
              className="flex items-center gap-1 rounded px-2 py-1 uppercase tracking-[0.16em]"
            >
              Problems
              {hasProblems ? (
                <span className="inline-flex h-4 min-w-[1.25rem] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white">
                  {validation.messages.length}
                </span>
              ) : null}
            </TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-2 text-[11px]">
            <label className="flex items-center gap-1 text-slate-500">
              Origin
              <select
                value={originFilter}
                onChange={(event) => setOriginFilter(event.target.value as typeof originFilter)}
                className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 shadow-sm"
              >
                <option value="all">All</option>
                <option value="run">Run</option>
                <option value="build">Build</option>
                <option value="raw">Raw</option>
              </select>
            </label>
            <label className="flex items-center gap-1 text-slate-500">
              Level
              <select
                value={levelFilter}
                onChange={(event) => setLevelFilter(event.target.value as typeof levelFilter)}
                className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 shadow-sm"
              >
                <option value="all">All</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="success">Success</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => setFollowLogs((prev) => !prev)}
              className={clsx(
                "rounded px-2 py-1 font-semibold uppercase tracking-wide transition",
                followLogs
                  ? "border border-emerald-500 bg-emerald-50 text-emerald-700"
                  : "border border-slate-300 bg-white text-slate-600 hover:border-slate-400",
              )}
            >
              {followLogs ? "Follow" : "Scroll"}
            </button>
            <button
              type="button"
              onClick={() => onClearConsole?.()}
              className="rounded border border-slate-300 bg-white px-2 py-1 font-semibold uppercase tracking-wide text-slate-600 transition hover:border-slate-400"
            >
              Clear
            </button>
          </div>
        </div>

        <TabsContent value="terminal" className="flex min-h-0 flex-1 flex-col">
          <TerminalPanel
            consoleLines={filteredConsoleLines}
            hasConsoleLines={hasConsoleLines}
            hasAnyConsoleLines={hasAnyConsoleLines}
            latestRun={latestRun}
            onShowRunDetails={onShowRunDetails}
            followLogs={followLogs}
          />
        </TabsContent>

        <TabsContent
          value="problems"
          className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm"
        >
          <ProblemsPanel validation={validation} />
        </TabsContent>

        <TabsContent
          value="runSummary"
          className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm"
        >
          <RunSummaryPanel latestRun={latestRun} />
        </TabsContent>
      </TabsRoot>
    </section>
  );
}

function TerminalPanel({
  consoleLines,
  hasConsoleLines,
  hasAnyConsoleLines,
  latestRun,
  onShowRunDetails,
  followLogs,
}: {
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly hasConsoleLines: boolean;
  readonly hasAnyConsoleLines: boolean;
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly onShowRunDetails?: () => void;
  readonly followLogs: boolean;
}) {
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!followLogs) return;
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [consoleLines, followLogs]);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-slate-900/80 bg-slate-950 font-mono text-[13px] leading-relaxed text-slate-100 shadow-inner shadow-black/30">
      <div className="flex flex-col border-b border-white/5 bg-slate-950/80">
        <div className="flex items-center gap-3 px-4 py-1.5 text-[11px] uppercase tracking-[0.35em] text-slate-500">
          <span className="font-semibold tracking-[0.45em] text-slate-200">Terminal</span>
          <span className="text-[10px] tracking-[0.45em] text-emerald-400">live</span>
        </div>
        {latestRun ? (
          <div className="flex items-center justify-between gap-3 border-t border-white/5 px-4 py-1.5 text-[11px] text-slate-400">
            <div className="flex min-w-0 items-center gap-2">
              <StatusDot status={latestRun.status} />
              <span className="truncate" title={latestRun.runId}>
                Run {latestRun.runId}
              </span>
              <span className="truncate text-slate-500">
                {latestRun.documentName ?? "Document not recorded"}
                {describeSheetSelection(latestRun.sheetNames) ? ` · ${describeSheetSelection(latestRun.sheetNames)}` : ""}
              </span>
              {latestRun.durationMs != null ? (
                <span className="text-slate-600">· {formatRunDuration(latestRun.durationMs)}</span>
              ) : null}
            </div>
            <button
              type="button"
              className="text-[11px] font-semibold text-emerald-300 transition hover:text-emerald-200"
              onClick={() => onShowRunDetails?.()}
            >
              View details →
            </button>
          </div>
        ) : null}
      </div>
      <div className="flex-1 overflow-auto">
        {hasConsoleLines ? (
          <ul className="divide-y divide-white/5">
            {consoleLines.map((line, index) => (
              <li
                key={`${line.timestamp ?? index}-${line.message}`}
                className="grid grid-cols-[auto_auto_1fr] items-baseline gap-4 px-4 py-1.5"
              >
                <span className="whitespace-nowrap text-[11px] tabular-nums text-slate-500">
                  {formatConsoleTimestamp(line.timestamp)}
                </span>
                <span
                  className={clsx("text-[10px] uppercase tracking-[0.3em]", consoleLevelClass(line.level))}
                >
                  {consoleLevelLabel(line.level)}
                </span>
                <span className="flex flex-wrap items-baseline gap-2 text-[13px] text-slate-100">
                  <span className={clsx("text-sm", consolePromptClass(line.level))}>$</span>
                  <span
                    className={clsx(
                      "flex-1 whitespace-pre-wrap break-words",
                      consoleLineClass(line.level),
                    )}
                  >
                    {line.message}
                  </span>
                </span>
              </li>
            ))}
            <div ref={logEndRef} />
          </ul>
        ) : hasAnyConsoleLines ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-slate-500">
            <p className="tracking-wide text-slate-300">No console output matches these filters.</p>
            <p className="text-[12px] leading-relaxed text-slate-500">Adjust origin or level filters to see more.</p>
          </div>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-slate-500">
            <p className="tracking-wide text-slate-300">Waiting for ADE output…</p>
            <p className="text-[12px] leading-relaxed text-slate-500">
              Run validation or a test to stream logs into this terminal.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ProblemsPanel({ validation }: { readonly validation: WorkbenchValidationState }) {
  const statusLabel = describeValidationStatus(validation);
  const fallbackMessage = describeValidationFallback(validation);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>{statusLabel}</span>
        {validation.lastRunAt ? <span>Last run {formatRelative(validation.lastRunAt)}</span> : null}
      </div>
      {validation.messages.length > 0 ? (
        <ul className="space-y-1.5">
          {validation.messages.map((item, index) => (
            <li key={`${item.level}-${item.path ?? index}-${index}`} className={validationMessageClass(item.level)}>
              {item.path ? (
                <span className="block text-[11px] font-medium uppercase tracking-wide text-slate-500">
                  {item.path}
                </span>
              ) : null}
              <span className="text-[13px]">{item.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs leading-relaxed text-slate-500">{fallbackMessage}</p>
      )}
    </div>
  );
}

function RunSummaryPanel({ latestRun }: { readonly latestRun?: WorkbenchRunSummary | null }) {
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
        <a
          href={`${summary.downloadBase}/logfile`}
          className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] font-semibold text-slate-700 shadow-sm hover:border-slate-300 hover:bg-white"
        >
          Download telemetry
        </a>
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
              : `${summary.downloadBase}/outputs/${encodedPath}`;
            return (
              <li
                key={file.path ?? file.name}
                className="flex items-center justify-between gap-2 break-all rounded border border-slate-100 px-2 py-1"
              >
                <a href={href} className="text-brand-600 hover:underline">
                  {file.name || file.path}
                </a>
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

function StatusDot({ status }: { readonly status: RunStatus }) {
  const tone =
    status === "succeeded"
      ? "bg-emerald-500"
      : status === "running" || status === "queued" || status === "active"
        ? "bg-amber-400"
      : status === "canceled"
        ? "bg-slate-400"
        : "bg-rose-500";

  return <span className={clsx("inline-block h-2.5 w-2.5 rounded-full", tone)} aria-hidden />;
}

const CONSOLE_PROMPTS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-[#569cd6]",
  warning: "text-[#dcdcaa]",
  error: "text-[#f48771]",
  success: "text-[#89d185]",
};

const CONSOLE_LINES: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-slate-100",
  warning: "text-amber-100",
  error: "text-rose-100",
  success: "text-emerald-100",
};

const CONSOLE_LEVELS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-slate-400",
  warning: "text-amber-400",
  error: "text-rose-400",
  success: "text-emerald-300",
};

const CONSOLE_LEVEL_LABELS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "INFO",
  warning: "WARN",
  error: "ERROR",
  success: "DONE",
};

function consolePromptClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_PROMPTS[level] ?? CONSOLE_PROMPTS.info;
}

function consoleLineClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LINES[level] ?? CONSOLE_LINES.info;
}

function consoleLevelClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LEVELS[level] ?? CONSOLE_LEVELS.info;
}

function consoleLevelLabel(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LEVEL_LABELS[level] ?? CONSOLE_LEVEL_LABELS.info;
}

function validationMessageClass(level: WorkbenchValidationState["messages"][number]["level"]) {
  switch (level) {
    case "error":
      return "text-danger-600";
    case "warning":
      return "text-amber-600";
    default:
      return "text-slate-600";
  }
}

function describeValidationStatus(validation: WorkbenchValidationState): string {
  switch (validation.status) {
    case "running":
      return "Running validation...";
    case "success": {
      if (validation.messages.length === 0) {
        return "Validation completed with no issues.";
      }
      const count = validation.messages.length;
      return `Validation completed with ${count} ${count === 1 ? "issue" : "issues"}.`;
    }
    case "error":
      return validation.error ?? "Validation failed.";
    default:
      return "No validation run yet.";
  }
}

function formatRelative(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function formatConsoleTimestamp(timestamp: WorkbenchConsoleLine["timestamp"]): string {
  if (!timestamp) {
    return " ";
  }
  const trimmed = timestamp.replace(/\s+/g, " ").trim();
  const longIso = Date.parse(trimmed);
  if (!Number.isNaN(longIso) && trimmed.includes("T")) {
    const date = new Date(longIso);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  return trimmed;
}

function describeValidationFallback(validation: WorkbenchValidationState): string {
  if (validation.status === "running") {
    return "Validation in progress...";
  }
  if (validation.status === "success") {
    return "No validation issues detected.";
  }
  if (validation.status === "error") {
    return validation.error ?? "Validation failed.";
  }
  return "Trigger validation from the workbench header to see ADE parsing results and manifest issues.";
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

function statusLabel(status: RunStatus): string {
  switch (status) {
    case "succeeded":
      return "Succeeded";
    case "failed":
      return "Failed";
    case "canceled":
      return "Canceled";
    case "queued":
      return "Queued";
    case "active":
    case "running":
      return "Running";
    default:
      return status;
  }
}

function describeSheetSelection(sheetNames?: readonly string[] | null): string | null {
  if (!sheetNames) {
    return null;
  }
  if (sheetNames.length === 0) {
    return "All worksheets";
  }
  return sheetNames.join(", ");
}

function resolveSeverity(level: WorkbenchConsoleLine["level"] | "all"): number {
  if (level === "error") return 3;
  if (level === "warning") return 2;
  if (level === "success") return 1;
  if (level === "info") return 1;
  return 0;
}
