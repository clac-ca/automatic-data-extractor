import type { ConfigBuilderPane } from "@app/nav/urlState";
import clsx from "clsx";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchConsoleLine, WorkbenchValidationState } from "../types";

interface BottomPanelProps {
  readonly height: number;
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly validation: WorkbenchValidationState;
  readonly activePane: ConfigBuilderPane;
  readonly onPaneChange: (pane: ConfigBuilderPane) => void;
}

export function BottomPanel({
  height,
  consoleLines,
  validation,
  activePane,
  onPaneChange,
}: BottomPanelProps) {
  const hasConsoleLines = consoleLines.length > 0;
  const statusLabel = describeValidationStatus(validation);
  const fallbackMessage = describeValidationFallback(validation);

  return (
    <section className="flex flex-col border-t border-slate-200 bg-slate-50" style={{ height }}>
      <TabsRoot value={activePane} onValueChange={(value) => onPaneChange(value as ConfigBuilderPane)}>
        <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
          <TabsList className="flex items-center gap-2">
            <TabsTrigger value="console" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Console
            </TabsTrigger>
            <TabsTrigger value="validation" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Validation
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="console" className="flex h-full flex-col">
          <div className="flex flex-1 flex-col overflow-hidden rounded-sm border border-slate-950/50 bg-[#050505] font-mono text-[13px] leading-relaxed text-[#e0e0e0] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
            <div className="flex items-center justify-between border-b border-white/5 bg-[#090909] px-4 py-2 text-[11px] uppercase tracking-[0.28em] text-[#8a8f98]">
              <div className="flex items-center gap-3">
                <span className="flex gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f56]" aria-hidden />
                  <span className="h-2.5 w-2.5 rounded-full bg-[#ffbd2e]" aria-hidden />
                  <span className="h-2.5 w-2.5 rounded-full bg-[#27c93f]" aria-hidden />
                </span>
                <span className="font-semibold tracking-[0.3em] text-[#c9cdd4]">ADE Terminal</span>
              </div>
              <span className="text-[10px] font-medium tracking-[0.35em] text-[#5d6168]">LIVE OUTPUT</span>
            </div>
            <div className="flex-1 overflow-auto bg-gradient-to-b from-[#050505] via-[#060606] to-[#040404]">
              {hasConsoleLines ? (
                <ul className="space-y-2 px-4 py-4">
                  {consoleLines.map((line, index) => (
                    <li
                      key={`${line.timestamp ?? index}-${line.message}`}
                      className="group grid grid-cols-[auto,1fr] items-start gap-4 rounded-lg border border-transparent px-3 py-2 transition hover:border-[#1f1f1f] hover:bg-[#0c0c0c]"
                    >
                      <span className="min-w-[8.5rem] text-[11px] tabular-nums text-[#8c8c8c] opacity-80 whitespace-nowrap">
                        {formatConsoleTimestamp(line.timestamp)}
                      </span>
                      <div className="flex flex-1 flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.4em] text-[#616161]">
                          <span className={clsx("rounded-full border px-2 py-0.5", consoleBadgeClass(line.level))}>
                            {consoleBadgeLabel(line.level)}
                          </span>
                          <span className="hidden text-[#2f2f2f] sm:inline">/workspace/config</span>
                        </div>
                        <div className="flex flex-wrap items-baseline gap-3">
                          <span className={clsx("text-sm font-semibold", consolePromptClass(line.level))}>$</span>
                          <span className={clsx("flex-1 whitespace-pre-wrap break-words", consoleLineClass(line.level))}>
                            {line.message}
                          </span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-[#7c7c7c]">
                  <p className="tracking-wide text-[#9da1aa]">Waiting for ADE output…</p>
                  <p className="text-[12px] leading-relaxed text-[#5c5c5c]">
                    Start a build or run validation to stream live logs in this terminal window.
                  </p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
        <TabsContent value="validation" className="flex-1 overflow-auto px-3 py-2 text-sm">
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

const CONSOLE_PROMPTS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-[#569cd6]",
  warning: "text-[#dcdcaa]",
  error: "text-[#f48771]",
  success: "text-[#89d185]",
};

const CONSOLE_LINES: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-[#d4d4d4]",
  warning: "text-[#dcdcaa]",
  error: "text-[#f48771]",
  success: "text-[#b6f0b1]",
};

const CONSOLE_BADGES: Record<WorkbenchConsoleLine["level"], string> = {
  info: "border-[#1d2633] bg-[#111827] text-[#93c5fd]",
  warning: "border-[#4b3b18] bg-[#372910] text-[#fcd34d]",
  error: "border-[#4a1d1d] bg-[#2b0f10] text-[#fca5a5]",
  success: "border-[#1f3d29] bg-[#112316] text-[#86efac]",
};

const CONSOLE_BADGE_LABELS: Record<WorkbenchConsoleLine["level"], string> = {
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

function consoleBadgeClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_BADGES[level] ?? CONSOLE_BADGES.info;
}

function consoleBadgeLabel(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_BADGE_LABELS[level] ?? CONSOLE_BADGE_LABELS.info;
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
