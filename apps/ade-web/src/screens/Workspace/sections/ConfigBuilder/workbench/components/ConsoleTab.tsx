import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode, UIEvent } from "react";
import clsx from "clsx";

import type { RunStreamStatus } from "../state/runStream";
import { formatConsoleTimestamp } from "../utils/console";
import type { WorkbenchConsoleLine, WorkbenchRunSummary } from "../types";
import { renderConsoleMessage, resolveSeverity } from "./consoleFormatting";

interface ConsoleTabProps {
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly onClearConsole?: () => void;
  readonly onShowRunDetails?: () => void;
  readonly runStatus?: RunStreamStatus;
}

type ConsoleFilters = {
  readonly origin: "all" | "run" | "build" | "raw";
  readonly level: "all" | WorkbenchConsoleLine["level"];
};

type RenderableConsoleLine = WorkbenchConsoleLine & {
  readonly key: string;
  readonly rendered: ReactNode;
};

export function ConsoleTab({
  consoleLines,
  latestRun,
  onClearConsole,
  onShowRunDetails,
  runStatus,
}: ConsoleTabProps) {
  const [filters, setFilters] = useState<ConsoleFilters>({ origin: "all", level: "all" });
  const [follow, setFollow] = useState(true);
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"parsed" | "raw">("parsed");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const filteredLines = useMemo(() => {
    const filterSeverity = resolveSeverity(filters.level);
    return consoleLines.filter((line) => {
      const originMatches = filters.origin === "all" || (line.origin ?? "run") === filters.origin;
      const severity = resolveSeverity(line.level);
      const levelMatches = filters.level === "all" || severity >= filterSeverity;
      return originMatches && levelMatches;
    });
  }, [consoleLines, filters]);

  const renderableLines: RenderableConsoleLine[] = useMemo(
    () =>
      filteredLines.map((line, index) => ({
        ...line,
        key: line.id ?? `${line.timestamp ?? "tbd"}-${line.origin ?? "run"}-${index}`,
        rendered: viewMode === "raw" ? renderRawEvent(line.raw ?? line.message) : renderConsoleMessage(line.message),
      })),
    [filteredLines, viewMode],
  );
  const copyContent = useMemo(
    () => filteredLines.map((line) => formatLineForCopy(line, viewMode)).join("\n"),
    [filteredLines, viewMode],
  );

  const hasConsoleLines = renderableLines.length > 0;
  const hasAnyConsoleLines = consoleLines.length > 0;
  const statusLabel = runStatus && runStatus !== "idle" ? runStatus : null;

  useEffect(() => {
    if (!follow) return;
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [renderableLines, follow]);

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
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  };

  const handleCopy = async () => {
    if (!copyContent) return;
    try {
      await navigator.clipboard?.writeText(copyContent);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-[#2a2a2a] bg-[#1e1e1e] font-mono text-[13px] leading-relaxed text-[#d4d4d4] shadow-[0_8px_24px_rgba(0,0,0,0.45)]">
      <div className="flex flex-col border-b border-[#2a2a2a] bg-gradient-to-r from-[#1f1f1f] to-[#232323]">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
          <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.22em] text-[#9da5b4]">
            <span className="font-semibold tracking-[0.3em] text-[#d4d4d4]">Terminal</span>
            <span className="text-[10px] tracking-[0.3em] text-emerald-400">live</span>
            {statusLabel ? (
              <span className="rounded-full border border-[#3a3a3a] bg-[#2b2b2b] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#d4d4d4]">
                {statusLabel}
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
            <label className="flex items-center gap-1 text-slate-400" title="Filter by event origin">
              Origin
              <select
                value={filters.origin}
                onChange={(event) => setFilters((prev) => ({ ...prev, origin: event.target.value as ConsoleFilters["origin"] }))}
                className="rounded border border-slate-700 bg-[#151515] px-2 py-1 text-[11px] text-slate-100 shadow-sm focus:border-emerald-500"
              >
                <option value="all">All</option>
                <option value="run">Run</option>
                <option value="build">Build</option>
                <option value="raw">Raw</option>
              </select>
            </label>
            <label className="flex items-center gap-1 text-slate-400" title="Filter by severity">
              Level
              <select
                value={filters.level}
                onChange={(event) => setFilters((prev) => ({ ...prev, level: event.target.value as ConsoleFilters["level"] }))}
                className="rounded border border-slate-700 bg-[#151515] px-2 py-1 text-[11px] text-slate-100 shadow-sm focus:border-emerald-500"
              >
                <option value="all">All</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="success">Success</option>
              </select>
            </label>
            <div className="flex items-center rounded border border-slate-600 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-200" title="Toggle between parsed view and raw JSON events">
              <button
                type="button"
                onClick={() => setViewMode("parsed")}
                className={clsx(
                  "px-2 py-[6px] transition",
                  viewMode === "parsed"
                    ? "bg-slate-700 text-white"
                    : "hover:bg-[#0f0f0f] text-slate-300",
                )}
              >
                Parsed
              </button>
              <button
                type="button"
                onClick={() => setViewMode("raw")}
                className={clsx(
                  "px-2 py-[6px] border-l border-slate-600 transition",
                  viewMode === "raw"
                    ? "bg-slate-700 text-white"
                    : "hover:bg-[#0f0f0f] text-slate-300",
                )}
              >
                Raw
              </button>
            </div>
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
            <button
              type="button"
              onClick={handleCopy}
              className={clsx(
                "rounded border px-2 py-[6px] text-[11px] font-semibold uppercase tracking-[0.14em] transition",
                copied
                  ? "border-emerald-600/60 bg-transparent text-emerald-200"
                  : "border border-slate-600 bg-transparent text-slate-200 hover:border-slate-400",
              )}
              disabled={!copyContent}
              title="Copy visible console output"
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
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-auto">
        {hasConsoleLines ? (
          <ul className="divide-y divide-[#252525]">
            {renderableLines.map((line) => (
              <li
                key={line.key}
                className="flex items-start gap-3 px-3 py-[2px] transition hover:bg-[#232323]"
              >
                <div className="flex min-w-0 flex-1 items-baseline gap-2">
                  {renderTimestamp(line.timestamp)}
                  <span className="shrink-0 font-mono text-[11px] leading-snug text-[#606674]">
                    {originLabel(line.origin)}
                  </span>
                  <span className={clsx("shrink-0 font-mono text-[11px] leading-snug", prefixTone(line.level))}>
                    {levelBadge(line.level)}
                  </span>
                  <div
                    className={clsx(
                      "min-w-0 whitespace-pre-wrap break-words text-[13px] leading-snug",
                      consoleMessageClass(line.level),
                    )}
                  >
                    {line.rendered}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : hasAnyConsoleLines ? (
          <EmptyState
            title="No console output matches these filters."
            description="Adjust origin or level filters to see more."
          />
        ) : (
          <EmptyState
            title="Waiting for ADE output…"
            description="Run validation or a test to stream logs into this terminal."
          />
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

function originLabel(origin?: WorkbenchConsoleLine["origin"]) {
  return origin === "build" ? "[build]" : origin === "raw" ? "[raw]" : "[run]";
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
  return (
    <span className="shrink-0 tabular-nums text-[11px] leading-snug text-[#7a8090]">
      [{formatted}]
    </span>
  );
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
  const formatted = formatConsoleTimestamp(value);
  if (formatted && formatted.trim().length > 0) return formatted;
  const raw = value.trim();
  return raw.length > 0 ? raw : "";
}

function renderRawEvent(raw: unknown) {
  if (typeof raw === "string") {
    return (
      <pre className="whitespace-pre-wrap break-words text-[12px] leading-snug text-[#d4d4d4]">
        {raw}
      </pre>
    );
  }
  if (raw && typeof raw === "object") {
    return (
      <pre className="whitespace-pre-wrap break-words text-[12px] leading-snug text-[#d4d4d4]">
        {JSON.stringify(raw, null, 2)}
      </pre>
    );
  }
  return null;
}
function formatLineForCopy(line: WorkbenchConsoleLine, viewMode: "parsed" | "raw") {
  const ts = displayTimestamp(line.timestamp);
  const origin = originLabel(line.origin);
  const level = consoleLevelLabel(line.level).toLowerCase();
  if (viewMode === "raw") {
    const rawString =
      typeof line.raw === "string"
        ? line.raw
        : line.raw
          ? JSON.stringify(line.raw, null, 2)
          : line.message ?? "";
    return `${ts ? `[${ts}] ` : ""}${origin} ${level} ${rawString}`.trim();
  }
  return `${ts ? `[${ts}] ` : ""}${origin} ${level} ${line.message ?? ""}`.trim();
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
