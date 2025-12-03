import clsx from "clsx";

import type { ConfigBuilderPane } from "@app/nav/urlState";
import type { PhaseState, RunStreamStatus } from "../state/runStream";
import type { WorkbenchConsoleLine, WorkbenchRunSummary, WorkbenchValidationState } from "../types";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import { ConsoleTab } from "./ConsoleTab";
import { ProblemsTab } from "./ProblemsTab";
import { RunSummaryTab } from "./RunSummaryTab";

interface BottomPanelProps {
  readonly height: number;
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly validation: WorkbenchValidationState;
  readonly activePane: ConfigBuilderPane;
  readonly onPaneChange: (pane: ConfigBuilderPane) => void;
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly onShowRunDetails?: () => void;
  readonly onClearConsole?: () => void;
  readonly runStatus?: RunStreamStatus;
  readonly buildPhases: Record<string, PhaseState>;
  readonly runPhases: Record<string, PhaseState>;
  readonly runMode?: "validation" | "extraction";
  readonly onToggleCollapse?: () => void;
  readonly appearance?: "light" | "dark";
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
  runStatus,
  buildPhases,
  runPhases,
  runMode,
  onToggleCollapse,
  appearance = "light",
}: BottomPanelProps) {
  const hasProblems = validation.messages.length > 0;
  const hasRun = Boolean(latestRun);
  const theme =
    appearance === "dark"
      ? {
          surface: "border-[#1f2431] bg-[#0f111a] text-slate-100",
          header: "border-[#1f2431] bg-[#0f111a]",
          hideButton:
            "border-[#2b3040] bg-[#161926] text-slate-100 hover:border-[#3b4153] hover:bg-[#1e2333]",
        }
      : {
          surface: "border-slate-200 bg-slate-50 text-slate-800",
          header: "border-slate-200 bg-slate-50",
          hideButton: "border-slate-300 bg-white text-slate-700 hover:border-slate-400",
        };
  const runStatusTone = appearance === "dark" ? "text-slate-300" : "text-slate-500";

  return (
    <section
      className={clsx("flex min-h-0 flex-col overflow-hidden border-t", theme.surface)}
      style={{ height }}
    >
      <TabsRoot
        value={activePane}
        onValueChange={(value) => onPaneChange(value as ConfigBuilderPane)}
      >
        <div
          className={clsx("flex flex-none items-center justify-between border-b px-3 py-1.5", theme.header)}
          onDoubleClick={onToggleCollapse}
          title={onToggleCollapse ? "Double-click to hide console" : undefined}
        >
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
                <span className={clsx("ml-1 text-[10px] lowercase", runStatusTone)}>
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
          {onToggleCollapse ? (
            <button
              type="button"
              onClick={onToggleCollapse}
              className={clsx(
                "rounded px-2 py-1 text-[11px] font-semibold uppercase tracking-wide shadow-sm transition",
                theme.hideButton,
              )}
              title="Hide console"
            >
              Hide
            </button>
          ) : null}
        </div>

        <TabsContent value="terminal" className="flex min-h-0 flex-1 flex-col">
          <ConsoleTab
            consoleLines={consoleLines}
            latestRun={latestRun}
            onClearConsole={onClearConsole}
            onShowRunDetails={onShowRunDetails}
            runStatus={runStatus}
          />
        </TabsContent>

        <TabsContent
          value="problems"
          className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm"
        >
          <ProblemsTab validation={validation} />
        </TabsContent>

        <TabsContent
          value="runSummary"
          className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm"
        >
          <RunSummaryTab latestRun={latestRun} buildPhases={buildPhases} runPhases={runPhases} runStatus={runStatus} runMode={runMode} />
        </TabsContent>
      </TabsRoot>
    </section>
  );
}
