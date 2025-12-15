import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { UIEvent } from "react";
import clsx from "clsx";
import { useVirtualizer } from "@tanstack/react-virtual";

import type { WorkbenchConsoleStore } from "../state/consoleStore";
import type { JobStreamStatus } from "../state/useJobStreamController";
import type { WorkbenchConsoleLine, WorkbenchRunSummary } from "../types";
import { formatConsoleLineNdjson, renderConsoleLine, resolveSeverity } from "./consoleFormatting";

interface ConsoleTabProps {
  readonly console: WorkbenchConsoleStore;
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly onClearConsole?: () => void;
  readonly runStatus?: JobStreamStatus;
}

type ConsoleFilters = {
  readonly origin: "all" | "run" | "build";
  readonly level: "all" | WorkbenchConsoleLine["level"];
};

type ConsoleViewMode = "parsed" | "ndjson";

const CONSOLE_LEVEL_STORAGE_KEY = "ade.ui.workbench.console.levelFilter.v1";

export function ConsoleTab({ console, latestRun, onClearConsole, runStatus }: ConsoleTabProps) {
  const [filters, setFilters] = useState<ConsoleFilters>(() => {
    const defaultFilters: ConsoleFilters = { origin: "all", level: "info" };
    if (typeof window === "undefined") return defaultFilters;
    try {
      const stored = window.localStorage.getItem(CONSOLE_LEVEL_STORAGE_KEY);
      if (
        stored === "all" ||
        stored === "debug" ||
        stored === "info" ||
        stored === "warning" ||
        stored === "error" ||
        stored === "success"
      ) {
        return { ...defaultFilters, level: stored };
      }
    } catch {
      // ignore localStorage failures
    }
    return defaultFilters;
  });
  const [follow, setFollow] = useState(true);
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<ConsoleViewMode>("parsed");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const snapshot = useSyncExternalStore(console.subscribe.bind(console), console.getSnapshot, console.getSnapshot);
  const totalLines = snapshot.length;

  const filteredIndices = useMemo(() => {
    const filterSeverity = resolveSeverity(filters.level);
    const indices: number[] = [];

    for (let index = 0; index < snapshot.length; index += 1) {
      const line = console.getLine(index);
      if (!line) continue;

      const originMatches = filters.origin === "all" || (line.origin ?? "run") === filters.origin;
      const severity = resolveSeverity(line.level);
      const levelMatches = filters.level === "all" || severity >= filterSeverity;
      if (originMatches && levelMatches) {
        indices.push(index);
      }
    }

    return indices;
  }, [console, snapshot, filters]);

  const hasConsoleLines = filteredIndices.length > 0;
  const hasAnyConsoleLines = totalLines > 0;
  const statusLabel = runStatus && runStatus !== "idle" ? runStatus : null;
  const clipboardAvailable = typeof navigator !== "undefined" && typeof navigator.clipboard?.writeText === "function";

  const rowVirtualizer = useVirtualizer({
    count: filteredIndices.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 22,
    overscan: 16,
  });

  useEffect(() => {
    if (!follow) return;
    if (filteredIndices.length === 0) return;
    rowVirtualizer.scrollToIndex(filteredIndices.length - 1, { align: "end" });
  }, [follow, filteredIndices.length, snapshot, rowVirtualizer]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(CONSOLE_LEVEL_STORAGE_KEY, filters.level);
    } catch {
      // ignore localStorage failures
    }
  }, [filters.level]);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    const el = event.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom < 16;
    if (!atBottom && follow) {
      setFollow(false);
    } else if (atBottom && !follow) {
      setFollow(true);
    }
  };

  const enableFollow = () => {
    setFollow(true);
    rowVirtualizer.scrollToIndex(filteredIndices.length - 1, { align: "end" });
  };

  const copyToClipboard = useCallback(async (text: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        // fall through to the fallback
      }
    }
    if (typeof document === "undefined") {
      return false;
    }
    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "true");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      const successful = document.execCommand("copy");
      document.body.removeChild(textarea);
      return successful;
    } catch {
      return false;
    }
  }, []);

  const handleCopy = async () => {
    if (!hasConsoleLines) return;
    const lines: string[] = [];
    for (const index of filteredIndices) {
      const line = console.getLine(index);
      if (!line) continue;
      lines.push(formatLineForCopy(line, viewMode));
    }
    const copiedSuccessfully = await copyToClipboard(lines.join("\n"));
    setCopied(copiedSuccessfully);
    if (copiedSuccessfully) {
      window.setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-[#2a2a2a] bg-[#1e1e1e] font-mono text-[13px] leading-relaxed text-[#d4d4d4] shadow-[0_8px_24px_rgba(0,0,0,0.45)]">
      <div className="flex flex-col border-b border-[#2a2a2a] bg-gradient-to-r from-[#1f1f1f] to-[#232323]">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
          <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.22em] text-[#9da5b4]">
            <span className="font-semibold tracking-[0.3em] text-slate-200">ADE</span>
            <span className="text-slate-400">Terminal</span>
            {statusLabel ? (
              <span className="rounded border border-slate-700 bg-[#151515] px-2 py-1 text-[10px] font-semibold tracking-[0.2em] text-slate-200">
                {statusLabel}
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            <label className="flex items-center gap-1 text-slate-400" title="Filter logs by scope">
              Origin
              <select
                value={filters.origin}
                onChange={(event) =>
                  setFilters((prev) => ({ ...prev, origin: event.target.value as ConsoleFilters["origin"] }))
                }
                className="rounded border border-slate-700 bg-[#151515] px-2 py-1 text-[11px] text-slate-100 shadow-sm focus:border-emerald-500"
              >
	                <option value="all">All</option>
	                <option value="run">Run</option>
	                <option value="build">Build</option>
	              </select>
            </label>
            <label className="flex items-center gap-1 text-slate-400" title="Filter by severity">
              Level
              <select
                value={filters.level}
                onChange={(event) =>
                  setFilters((prev) => ({ ...prev, level: event.target.value as ConsoleFilters["level"] }))
                }
                className="rounded border border-slate-700 bg-[#151515] px-2 py-1 text-[11px] text-slate-100 shadow-sm focus:border-emerald-500"
              >
                <option value="all">All</option>
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="success">Success</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => (follow ? setFollow(false) : enableFollow())}
              className={clsx(
                "rounded px-2 py-[6px] text-[11px] font-semibold uppercase tracking-[0.14em] transition",
                follow
                  ? "border border-emerald-600/60 bg-transparent text-emerald-200"
                  : "border border-slate-600 bg-transparent text-slate-200 hover:border-slate-400",
              )}
              title="Auto-scroll to newest logs"
            >
              {follow ? "Following" : "Follow"}
            </button>
            <div className="flex items-center gap-2" title="Toggle between parsed view and raw NDJSON">
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">View</span>
              <div role="radiogroup" aria-label="Console view mode" className="flex items-center gap-1">
                <button
                  type="button"
                  role="radio"
                  aria-checked={viewMode === "parsed"}
                  onClick={() => setViewMode("parsed")}
                  className={clsx(
                    "rounded border px-2 py-[6px] text-[11px] font-semibold uppercase tracking-[0.14em] transition focus:outline-none focus:ring-1 focus:ring-emerald-500",
                    viewMode === "parsed"
                      ? "border-emerald-600/70 text-emerald-200"
                      : "border-slate-600 text-slate-200 hover:border-slate-400",
                  )}
                >
                  Parsed
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={viewMode === "ndjson"}
                  onClick={() => setViewMode("ndjson")}
                  className={clsx(
                    "rounded border px-2 py-[6px] text-[11px] font-semibold uppercase tracking-[0.14em] transition focus:outline-none focus:ring-1 focus:ring-emerald-500",
                    viewMode === "ndjson"
                      ? "border-emerald-600/70 text-emerald-200"
                      : "border-slate-600 text-slate-200 hover:border-slate-400",
                  )}
                >
                  NDJSON
                </button>
              </div>
            </div>
            <button
              type="button"
              onClick={handleCopy}
              className={clsx(
                "rounded border px-2 py-[6px] text-[11px] font-semibold uppercase tracking-[0.14em] transition",
                copied
                  ? "border-emerald-600/60 bg-transparent text-emerald-200"
                  : "border border-slate-600 bg-transparent text-slate-200 hover:border-slate-400",
              )}
              disabled={!hasConsoleLines}
              title={clipboardAvailable ? "Copy visible console output" : "Copy may be blocked by browser permissions"}
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={() => onClearConsole?.()}
              className="rounded border border-slate-600 bg-[#0f0f0f] px-2 py-[6px] text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-200 transition hover:border-slate-400"
              title="Clear console output"
            >
              Clear
            </button>
          </div>
        </div>
        {latestRun ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#2a2a2a] bg-[#181818] px-4 py-1.5 text-[11px] text-[#7f8794]">
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
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">Downloads</span>
              <RunArtifactLink
                href={latestRun.outputUrl}
                label={latestRun.outputFilename ? `Output (${latestRun.outputFilename})` : "Output"}
                disabledLabel="Output (not ready)"
                disabledReason="Output is not available for this run."
              />
              <RunArtifactLink
                href={latestRun.logsUrl}
                label="Events (NDJSON)"
                disabledLabel="Events"
                disabledReason="Events log is not available."
              />
              <RunArtifactLink
                href={latestRun.inputUrl}
                label="Input"
                disabledLabel="Input"
                disabledReason="Input file download is not available."
              />
            </div>
          </div>
        ) : null}
      </div>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto bg-[#1e1e1e] [color-scheme:dark]"
        style={{ scrollbarColor: "#2f2f2f #111111" }}
      >
        {hasConsoleLines ? (
          <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative" }}>
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const lineIndex = filteredIndices[virtualRow.index];
              const line = typeof lineIndex === "number" ? console.getLine(lineIndex) : undefined;
              if (!line) return null;

              const key = line.id ?? `${line.timestamp ?? "tbd"}-${line.origin ?? "run"}-${lineIndex}`;
              const rendered =
                viewMode === "ndjson" ? (
                  <span className="whitespace-pre-wrap break-words">
                    {formatConsoleLineNdjson(line) ?? line.message}
                  </span>
                ) : (
                  renderConsoleLine(line)
                );

              return (
                <div
                  key={key}
                  data-index={virtualRow.index}
                  ref={rowVirtualizer.measureElement}
                  className="flex items-start gap-3 border-b border-[#1a1a1a] px-3 py-[2px] transition hover:bg-[#232323] last:border-b-0"
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <div className="flex min-w-0 flex-1 items-baseline gap-2">
                    {renderTimestamp(line.timestamp)}
                    <span className="shrink-0 w-12 text-right font-mono text-[11px] leading-snug text-[#606674]">
                      {originLabel(line.origin)}
                    </span>
                    <span
                      className={clsx(
                        "shrink-0 w-14 text-right font-mono text-[11px] leading-snug",
                        prefixTone(line.level),
                      )}
                    >
                      {levelBadge(line.level)}
                    </span>
                    <div
                      className={clsx(
                        "min-w-0 whitespace-pre-wrap break-words text-[13px] leading-snug",
                        consoleMessageClass(line.level),
                      )}
                    >
                      {rendered}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : hasAnyConsoleLines ? (
          <EmptyState title="No console output matches these filters." description="Adjust origin or level filters to see more." />
        ) : (
          <EmptyState title="Waiting for ADE output…" description="Run validation or a test to stream logs into this terminal." />
        )}
      </div>
    </div>
  );
}

function EmptyState({ title, description }: { readonly title: string; readonly description: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-slate-500">
      <p className="tracking-wide text-slate-300">{title}</p>
      <p className="text-[12px] leading-relaxed text-slate-500">{description}</p>
    </div>
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

function consoleMessageClass(level: WorkbenchConsoleLine["level"]) {
  switch (level) {
    case "warning":
      return "text-amber-100";
    case "error":
      return "text-rose-100";
    case "success":
      return "text-emerald-100";
    default:
      return "text-[#d4d4d4]";
  }
}

function consoleLevelLabel(level: WorkbenchConsoleLine["level"]) {
  switch (level) {
    case "warning":
      return "WARN";
    case "error":
      return "ERROR";
    case "success":
      return "DONE";
    default:
      return "INFO";
  }
}

function isCancelledStatus(status?: WorkbenchRunSummary["status"]) {
  return status === "cancelled";
}

function originLabel(origin?: WorkbenchConsoleLine["origin"]) {
  return origin === "build" ? "[build]" : "[run]";
}

function renderTimestamp(timestamp?: string) {
  const formatted = displayTimestamp(timestamp);
  if (!formatted) {
    return (
      <span className="shrink-0 tabular-nums text-[11px] leading-snug text-[#4f5665]" aria-hidden>
        ·
      </span>
    );
  }
  return <span className="shrink-0 tabular-nums text-[11px] leading-snug text-[#7a8090]">[{formatted}]</span>;
}

function levelBadge(level: WorkbenchConsoleLine["level"]) {
  switch (level) {
    case "warning":
      return "• warn";
    case "error":
      return "• error";
    case "success":
      return "• done";
    default:
      return "• info";
  }
}

function prefixTone(level: WorkbenchConsoleLine["level"]) {
  switch (level) {
    case "warning":
      return "text-amber-300";
    case "error":
      return "text-rose-300";
    case "success":
      return "text-emerald-300";
    default:
      return "text-[#6f7683]";
  }
}

function displayTimestamp(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
  const raw = value.trim();
  return raw.length > 0 ? raw : "";
}

function formatLineForCopy(line: WorkbenchConsoleLine, mode: ConsoleViewMode) {
  const ts = displayTimestamp(line.timestamp);
  const origin = originLabel(line.origin);
  const level = consoleLevelLabel(line.level).toLowerCase();
  const msg =
    mode === "ndjson" ? formatConsoleLineNdjson(line) ?? line.message ?? "" : line.message ?? "";
  return `${ts ? `[${ts}] ` : ""}${origin} ${level} ${msg}`.trim();
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

function RunArtifactLink({
  href,
  label,
  disabledLabel,
  disabledReason,
}: {
  readonly href?: string;
  readonly label: string;
  readonly disabledLabel: string;
  readonly disabledReason: string;
}) {
  const available = typeof href === "string" && href.trim().length > 0;
  const base =
    "inline-flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] transition";
  const enabledClass = "border-slate-700 bg-[#101010] text-slate-200 hover:border-slate-500";
  const disabledClass = "border-slate-800 bg-[#0f0f0f] text-slate-600 cursor-not-allowed";

  if (!available) {
    return (
      <span className={clsx(base, disabledClass)} title={disabledReason}>
        {disabledLabel}
      </span>
    );
  }

  return (
    <a className={clsx(base, enabledClass)} href={href} title={label}>
      <DownloadIcon />
      <span className="truncate">{label}</span>
    </a>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-slate-300" fill="none" aria-hidden>
      <path
        d="M10 3v8m0 0 3-3m-3 3-3-3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 13.5v2A1.5 1.5 0 0 0 5.5 17h9A1.5 1.5 0 0 0 16 15.5v-2"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
