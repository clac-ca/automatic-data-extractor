import type { ConfigBuilderPane } from "@app/nav/urlState";
import type { RunStreamStatus } from "../state/runStream";
import type {
  WorkbenchConsoleLine,
  WorkbenchRunSummary,
  WorkbenchValidationState,
} from "../types";

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
}: BottomPanelProps) {
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
          <RunSummaryTab latestRun={latestRun} />
        </TabsContent>
      </TabsRoot>
    </section>
  );
}
