import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from "react";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { Problem, RunLogLine } from "../adapters/types";

interface ConsolePanelProps {
  readonly isOpen: boolean;
  readonly height: number;
  readonly onResize: (nextHeight: number) => void;
  readonly onToggle: () => void;
  readonly logs: readonly RunLogLine[];
  readonly problems: readonly Problem[];
  readonly onClearLogs: () => void;
  readonly onSelectProblem: (problem: Problem) => void;
}

type ConsoleTab = "logs" | "problems";

export function ConsolePanel({
  isOpen,
  height,
  onResize,
  onToggle,
  logs,
  problems,
  onClearLogs,
  onSelectProblem,
}: ConsolePanelProps) {
  const [tab, setTab] = useState<ConsoleTab>("logs");
  const [isDragging, setDragging] = useState(false);

  const handleTabChange = (next: string) => {
    if (next === "logs" || next === "problems") {
      setTab(next);
    }
  };

  useEffect(() => {
    if (!isDragging) {
      return;
    }
    const handleMove = (event: MouseEvent) => {
      onResize(Math.max(120, window.innerHeight - event.clientY - 80));
    };
    const handleUp = () => setDragging(false);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [isDragging, onResize]);

  const handleDragStart = (event: ReactMouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(true);
  };

  const hasProblems = problems.length > 0;

  const visibleLogs = useMemo(() => logs.slice(-200), [logs]);

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center justify-between rounded-t-2xl border border-slate-800/40 bg-slate-900/80 px-4 py-2 text-xs uppercase tracking-wide text-slate-300"
      >
        Console
        <span className="text-slate-500">Show</span>
      </button>
    );
  }

  return (
    <TabsRoot value={tab} onValueChange={handleTabChange}>
      <div className="relative flex flex-col rounded-t-2xl border border-slate-800/40 bg-slate-950/90" style={{ height }}>
        <div
          className="absolute inset-x-0 top-0 h-2 cursor-row-resize rounded-t-2xl"
          onMouseDown={handleDragStart}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize console"
        />
        <header className="flex items-center justify-between border-b border-slate-800/60 px-4 py-2 text-xs text-slate-300">
          <TabsList className="flex items-center gap-3">
            <TabsTrigger
              value="logs"
              className={`rounded-full px-3 py-1 font-medium ${
                tab === "logs" ? "bg-brand-500/20 text-white" : "hover:bg-slate-800/60"
              }`}
            >
              Logs
            </TabsTrigger>
            <TabsTrigger
              value="problems"
              className={`rounded-full px-3 py-1 font-medium ${
                tab === "problems" ? "bg-brand-500/20 text-white" : "hover:bg-slate-800/60"
              }`}
            >
              Problems
              {hasProblems ? (
                <span className="ml-2 rounded-full bg-amber-500/20 px-2 text-[10px] text-amber-300">{problems.length}</span>
              ) : null}
            </TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onClearLogs} className="rounded px-2 py-1 text-slate-400 hover:bg-slate-800/60">
              Clear
            </button>
            <button type="button" onClick={onToggle} className="rounded px-2 py-1 text-slate-400 hover:bg-slate-800/60">
              Close
            </button>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 text-sm">
          <TabsContent value="logs" className="h-full" aria-live="polite">
            <ul className="space-y-1 text-[13px] text-slate-200">
              {visibleLogs.length === 0 ? <li className="text-slate-500">No log output yet.</li> : null}
              {visibleLogs.map((log, index) => (
                <li key={`${log.ts}-${index}`} className="flex items-start gap-3">
                  <span className="text-xs text-slate-500">{new Date(log.ts).toLocaleTimeString()}</span>
                  <span className="whitespace-pre-wrap">{log.text}</span>
                </li>
              ))}
            </ul>
          </TabsContent>
          <TabsContent value="problems" className="h-full">
            <ul className="space-y-2 text-[13px] text-slate-200">
              {problems.length === 0 ? <li className="text-slate-500">No problems detected.</li> : null}
              {problems.map((problem) => (
                <li
                  key={`${problem.path}:${problem.line ?? ""}:${problem.message}`}
                  className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3"
                >
                  <button
                    type="button"
                    className="text-left text-sm font-medium text-amber-200 hover:underline"
                    onClick={() => onSelectProblem(problem)}
                  >
                    {problem.path}
                    {problem.line ? `:${problem.line}` : ""}
                  </button>
                  <p className="mt-1 text-xs text-amber-100">{problem.message}</p>
                </li>
              ))}
            </ul>
          </TabsContent>
        </div>
      </div>
    </TabsRoot>
  );
}
