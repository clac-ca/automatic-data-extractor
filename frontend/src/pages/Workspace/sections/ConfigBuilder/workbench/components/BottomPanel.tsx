import clsx from "clsx";

import type { WorkbenchPane } from "../state/workbenchSearchParams";
import type { JobStreamStatus } from "../state/useJobStreamController";
import type { WorkbenchConsoleStore } from "../state/consoleStore";
import type { WorkbenchRunSummary, WorkbenchValidationState } from "../types";

import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";

import { ConsoleTab } from "./ConsoleTab";
import { ProblemsTab } from "./ProblemsTab";

interface BottomPanelProps {
  readonly height: number;
  readonly console: WorkbenchConsoleStore;
  readonly validation: WorkbenchValidationState;
  readonly activePane: WorkbenchPane;
  readonly onPaneChange: (pane: WorkbenchPane) => void;
  readonly latestRun?: WorkbenchRunSummary | null;
  readonly onClearConsole?: () => void;
  readonly runStatus?: JobStreamStatus;
  readonly onToggleCollapse?: () => void;
  readonly appearance?: "light" | "dark";
}

export function BottomPanel({
  height,
  console,
  validation,
  activePane,
  onPaneChange,
  latestRun,
  onClearConsole,
  runStatus,
  onToggleCollapse,
  appearance = "light",
}: BottomPanelProps) {
  const hasProblems = validation.messages.length > 0;
  const theme =
    appearance === "dark"
      ? {
          surface: "border-border bg-card text-foreground",
          header: "border-border bg-card",
          hideButton: "border-border bg-popover text-foreground hover:border-ring/40 hover:bg-muted",
        }
      : {
          surface: "border-border bg-muted text-foreground",
          header: "border-border bg-muted",
          hideButton: "border-border bg-card text-foreground hover:border-ring/40 hover:bg-muted",
        };

  return (
    <section
      className={clsx("flex min-h-0 flex-col overflow-hidden border-t", theme.surface)}
      style={{ height }}
    >
      <TabsRoot
        value={activePane}
        onValueChange={(value) => onPaneChange(value as WorkbenchPane)}
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
              value="problems"
              className="flex items-center gap-1 rounded px-2 py-1 uppercase tracking-[0.16em]"
            >
              Problems
              {hasProblems ? (
                <span className="inline-flex h-4 min-w-[1.25rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
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
            console={console}
            latestRun={latestRun}
            onClearConsole={onClearConsole}
            runStatus={runStatus}
          />
        </TabsContent>

        <TabsContent
          value="problems"
          className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm"
        >
          <ProblemsTab validation={validation} />
        </TabsContent>
      </TabsRoot>
    </section>
  );
}
