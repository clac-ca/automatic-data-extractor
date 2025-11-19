import type { ConfigBuilderPane } from "@app/nav/urlState";
import type { RunStatus } from "@shared/runs/types";
import clsx from "clsx";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchConsoleLine, WorkbenchValidationState } from "../types";

export interface WorkbenchRunSummary {
  readonly runId: string;
  readonly status: RunStatus;
  readonly downloadBase: string;
  readonly outputs: ReadonlyArray<{ path: string; byte_size: number }>;
  readonly outputsLoaded: boolean;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
  readonly error?: string | null;
}

interface BottomPanelProps {
  readonly height: number;
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly validation: WorkbenchValidationState;
  readonly activePane: ConfigBuilderPane;
  readonly onPaneChange: (pane: ConfigBuilderPane) => void;
  readonly latestRun?: WorkbenchRunSummary | null;
}

export function BottomPanel({
  height,
  consoleLines,
  validation,
  activePane,
  onPaneChange,
  latestRun,
}: BottomPanelProps) {
  const hasConsoleLines = consoleLines.length > 0;
  const statusLabel = describeValidationStatus(validation);
  const fallbackMessage = describeValidationFallback(validation);

  return (
    <section className="flex min-h-0 flex-col overflow-hidden border-t border-slate-200 bg-slate-50" style={{ height }}>
      <TabsRoot value={activePane} onValueChange={(value) => onPaneChange(value as ConfigBuilderPane)}>
        <div className="flex flex-none items-center justify-between border-b border-slate-200 px-3 py-2">
          <TabsList className="flex items-center gap-2">
            <TabsTrigger value="console" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Console
            </TabsTrigger>
            <TabsTrigger value="validation" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Validation
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="console" className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-slate-900/80 bg-slate-950 font-mono text-[13px] leading-relaxed text-slate-100 shadow-inner shadow-black/30">
            <div className="flex flex-none items-center gap-3 border-b border-white/5 bg-slate-950/80 px-4 py-2 text-[11px] uppercase tracking-[0.35em] text-slate-500">
              <span className="font-semibold tracking-[0.45em] text-slate-200">Terminal</span>
              <span className="text-[10px] tracking-[0.45em] text-emerald-400">live</span>
            </div>
            <div className="flex-1 overflow-auto">
              {latestRun ? <RunSummaryCard summary={latestRun} /> : null}
              {hasConsoleLines ? (
                <ul className="divide-y divide-white/5">
                  {consoleLines.map((line, index) => (
                    <li
                      key={`${line.timestamp ?? index}-${line.message}`}
                      className="grid grid-cols-[auto_auto_1fr] items-baseline gap-4 px-4 py-2"
                    >
                      <span className="text-[11px] text-slate-500 tabular-nums whitespace-nowrap">
                        {formatConsoleTimestamp(line.timestamp)}
                      </span>
                      <span className={clsx("text-[11px] uppercase tracking-[0.3em]", consoleLevelClass(line.level))}>
                        {consoleLevelLabel(line.level)}
                      </span>
                      <span className="flex flex-wrap items-baseline gap-2 text-[13px] text-slate-100">
                        <span className={clsx("text-sm", consolePromptClass(line.level))}>$</span>
                        <span className={clsx("flex-1 whitespace-pre-wrap break-words", consoleLineClass(line.level))}>
                          {line.message}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-slate-500">
                  <p className="tracking-wide text-slate-300">Waiting for ADE output…</p>
                  <p className="text-[12px] leading-relaxed text-slate-500">
                    Start a build or run validation to stream live logs in this terminal window.
                  </p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
        <TabsContent value="validation" className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>{statusLabel}</span>
              {validation.lastRunAt ? <span>Last run {formatRelative(validation.lastRunAt)}</span> : null}
            </div>
            {validation.messages.length > 0 ? (
              <ul className="space-y-2">
                {validation.messages.map((item, index) => (
                  <li key={`${item.level}-${item.path ?? index}-${index}`} className={validationMessageClass(item.level)}>
                    {item.path ? (
                      <span className="block text-xs font-medium uppercase tracking-wide text-slate-500">{item.path}</span>
                    ) : null}
                    <span>{item.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs leading-relaxed text-slate-500">{fallbackMessage}</p>
            )}
          </div>
        </TabsContent>
      </TabsRoot>
    </section>
  );
}

function RunSummaryCard({ summary }: { summary: WorkbenchRunSummary }) {
  const statusLabel = summary.status.charAt(0).toUpperCase() + summary.status.slice(1);
  return (
    <section className="border-b border-white/5 bg-slate-900/60 px-4 py-3 text-[13px] text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-50" title={summary.runId}>
            Run {summary.runId}
          </p>
          <p className="text-xs text-slate-400">Status: {statusLabel}</p>
          {summary.documentName ? (
            <p className="text-xs text-slate-400">Document: {summary.documentName}</p>
          ) : null}
          {summary.sheetNames ? (
            <p className="text-xs text-slate-400">
              Worksheets:
              {summary.sheetNames.length === 0
                ? " All worksheets"
                : ` ${summary.sheetNames.join(", ")}`}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={`${summary.downloadBase}/artifact`}
            className="inline-flex items-center rounded border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-800"
          >
            Download artifact
          </a>
          <a
            href={`${summary.downloadBase}/logfile`}
            className="inline-flex items-center rounded border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-800"
          >
            Download logs
          </a>
        </div>
      </div>
      <div className="mt-3 rounded-md border border-white/10 bg-slate-950/70 px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Output files</p>
        {summary.error ? (
          <p className="text-xs text-rose-300">{summary.error}</p>
        ) : !summary.outputsLoaded ? (
          <p className="text-xs text-slate-400">Loading outputs…</p>
        ) : summary.outputs.length > 0 ? (
          <ul className="mt-2 space-y-1 text-xs text-slate-100">
            {summary.outputs.map((file) => (
              <li key={file.path} className="flex items-center justify-between gap-2 break-all rounded border border-white/10 px-2 py-1">
                <a
                  href={`${summary.downloadBase}/outputs/${file.path.split("/").map(encodeURIComponent).join("/")}`}
                  className="text-emerald-400 hover:underline"
                >
                  {file.path}
                </a>
                <span className="text-[11px] text-slate-400">{file.byte_size.toLocaleString()} bytes</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-slate-400">No output files were generated.</p>
        )}
      </div>
    </section>
  );
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
    case "success":
      return "text-emerald-600";
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
  // Keep ISO timestamps readable while preventing multi-line wrapping.
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
