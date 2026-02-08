import clsx from "clsx";
import type { MouseEventHandler, ReactNode } from "react";

import { useSidebar } from "@/components/ui/sidebar";
import {
  ActionsIcon,
  CloseIcon,
  ConsoleIcon,
  GridIcon,
  MinimizeIcon,
  RunIcon,
  SaveIcon,
  SidebarIcon,
  SpinnerIcon,
  WindowMaximizeIcon,
  WindowRestoreIcon,
} from "@/components/icons";

interface WorkbenchChromeProps {
  readonly configName: string;
  readonly workspaceLabel: string;
  readonly validationLabel?: string;
  readonly canSaveFiles: boolean;
  readonly isSavingFiles: boolean;
  readonly onSaveFile: () => void;
  readonly saveShortcutLabel: string;
  readonly onOpenActionsMenu: (position: { x: number; y: number }) => void;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly canPublish: boolean;
  readonly isPublishing: boolean;
  readonly onPublish: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: () => void;
  readonly consoleOpen: boolean;
  readonly onToggleConsole: () => void;
  readonly consoleToggleDisabled?: boolean;
  readonly appearance: "light" | "dark";
  readonly windowState: "restored" | "maximized";
  readonly onMinimizeWindow: () => void;
  readonly onToggleMaximize: () => void;
  readonly onCloseWindow: () => void;
  readonly actionsBusy?: boolean;
}

export function WorkbenchChrome({
  configName,
  workspaceLabel,
  validationLabel,
  canSaveFiles,
  isSavingFiles,
  onSaveFile,
  saveShortcutLabel,
  onOpenActionsMenu,
  canRunValidation,
  isRunningValidation,
  onRunValidation,
  canPublish,
  isPublishing,
  onPublish,
  canRunExtraction,
  isRunningExtraction,
  onRunExtraction,
  consoleOpen,
  onToggleConsole,
  consoleToggleDisabled = false,
  appearance,
  windowState,
  onMinimizeWindow,
  onToggleMaximize,
  onCloseWindow,
  actionsBusy = false,
}: WorkbenchChromeProps) {
  const surfaceClass = "border-border bg-card text-foreground";
  const metaTextClass = "text-muted-foreground";
  const saveButtonClass =
    "bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground";
  const runButtonClass =
    "bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground";
  const isMaximized = windowState === "maximized";
  const { state, openMobile, isMobile, toggleSidebar } = useSidebar();
  const explorerVisible = isMobile ? openMobile : state === "expanded";
  return (
    <div className={clsx("flex items-center justify-between border-b px-4 py-2", surfaceClass)}>
      <div className="flex min-w-0 items-center gap-3">
        <WorkbenchBadgeIcon />
        <div className="min-w-0 leading-tight">
          <div className={clsx("text-[10px] font-semibold uppercase tracking-[0.35em]", metaTextClass)}>
            Config Workbench
          </div>
          <div className="truncate text-sm font-semibold" title={configName}>
            {configName}
          </div>
          <div className={clsx("text-[11px]", metaTextClass)} title={workspaceLabel}>
            Workspace · {workspaceLabel}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {validationLabel ? <span className={clsx("text-xs", metaTextClass)}>{validationLabel}</span> : null}
        <button
          type="button"
          onClick={onSaveFile}
          disabled={!canSaveFiles}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            saveButtonClass,
          )}
          title={`Save (${saveShortcutLabel})`}
        >
          {isSavingFiles ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <SaveIcon className="h-4 w-4" />}
          {isSavingFiles ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onRunValidation}
          disabled={!canRunValidation}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningValidation ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          {isRunningValidation ? "Running…" : "Run validation"}
        </button>
        <button
          type="button"
          onClick={onPublish}
          disabled={!canPublish}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isPublishing ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          {isPublishing ? "Publishing…" : "Publish"}
        </button>
        <button
          type="button"
          onClick={onRunExtraction}
          disabled={!canRunExtraction}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
          title="Run test run"
        >
          {isRunningExtraction ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          {isRunningExtraction ? "Running…" : "Test run"}
        </button>
        <div className="flex items-center gap-1">
          <ChromeIconButton
            ariaLabel={explorerVisible ? "Hide sidebar" : "Show sidebar"}
            onClick={toggleSidebar}
            appearance={appearance}
            active={explorerVisible}
            icon={<SidebarIcon className={clsx("h-4 w-4", !explorerVisible && "opacity-60")} />}
          />
          <ChromeIconButton
            ariaLabel={consoleOpen ? "Hide console" : "Show console"}
            onClick={onToggleConsole}
            appearance={appearance}
            active={consoleOpen}
            disabled={consoleToggleDisabled}
            icon={<ConsoleIcon className="h-3.5 w-3.5" />}
          />
        </div>
        <ChromeIconButton
          ariaLabel="Configuration actions"
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            onOpenActionsMenu({ x: rect.right + 8, y: rect.bottom });
          }}
          appearance={appearance}
          disabled={actionsBusy}
          icon={<ActionsIcon className="h-4 w-4" />}
        />
        <div
          className={clsx(
            "flex items-center gap-2 border-l pl-3",
            "border-border/70",
          )}
        >
          <ChromeIconButton
            ariaLabel="Minimize workbench"
            onClick={onMinimizeWindow}
            appearance={appearance}
            icon={<MinimizeIcon className="h-3.5 w-3.5" />}
          />
          <ChromeIconButton
            ariaLabel={isMaximized ? "Restore workbench" : "Maximize workbench"}
            onClick={onToggleMaximize}
            appearance={appearance}
            active={isMaximized}
            icon={
              isMaximized ? <WindowRestoreIcon className="h-3.5 w-3.5" /> : <WindowMaximizeIcon className="h-3.5 w-3.5" />
            }
          />
          <ChromeIconButton
            ariaLabel="Close workbench"
            onClick={onCloseWindow}
            appearance={appearance}
            icon={<CloseIcon className="h-3.5 w-3.5" />}
          />
        </div>
      </div>
    </div>
  );
}

function ChromeIconButton({
  ariaLabel,
  onClick,
  icon,
  appearance: _appearance,
  active = false,
  disabled = false,
}: {
  readonly ariaLabel: string;
  readonly onClick: MouseEventHandler<HTMLButtonElement>;
  readonly icon: ReactNode;
  readonly appearance: "light" | "dark";
  readonly active?: boolean;
  readonly disabled?: boolean;
}) {
  const baseClass =
    "text-muted-foreground hover:text-foreground hover:bg-muted hover:border-ring/40 focus-visible:ring-ring/40";
  const activeClass = "text-foreground border-ring bg-muted";
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "flex h-7 w-7 items-center justify-center rounded-[4px] border border-transparent text-sm transition focus-visible:outline-none focus-visible:ring-2",
        baseClass,
        active && activeClass,
        disabled && "cursor-not-allowed opacity-50",
      )}
      title={ariaLabel}
    >
      {icon}
    </button>
  );
}

function WorkbenchBadgeIcon() {
  return (
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-md">
      <GridIcon className="h-4 w-4" />
    </span>
  );
}
