import clsx from "clsx";
import type { MouseEventHandler, ReactNode } from "react";
import {
  FilePlus2,
  FolderOpen,
  XSquare,
} from "lucide-react";

import { useSidebar } from "@/components/ui/sidebar";
import {
  ActionsIcon,
  CloseIcon,
  ConsoleIcon,
  CopyIcon,
  EditIcon,
  GridIcon,
  RunIcon,
  SaveIcon,
  SidebarIcon,
  SpinnerIcon,
} from "@/components/icons";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfigurationTitleMenu } from "./ConfigurationTitleMenu";

interface WorkbenchChromeProps {
  readonly configName: string;
  readonly configStatus: string;
  readonly workspaceLabel: string;
  readonly validationLabel?: string;
  readonly canSaveFiles: boolean;
  readonly isSavingFiles: boolean;
  readonly onSaveFile: () => void;
  readonly saveShortcutLabel: string;
  readonly toggleConsoleShortcutLabel: string;
  readonly onOpenActionsMenu: (position: { x: number; y: number }) => void;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly onOpenConfigurationsHome: () => void;
  readonly onCreateConfigurationFromFileMenu: () => void;
  readonly onCloseFromFileMenu: () => void;
  readonly canPublish: boolean;
  readonly isPublishing: boolean;
  readonly onPublish: () => void;
  readonly canRenameConfiguration: boolean;
  readonly canArchiveDraft: boolean;
  readonly titleMenuOpen: boolean;
  readonly onTitleMenuOpenChange: (open: boolean) => void;
  readonly onRenameConfiguration: () => void;
  readonly onCopyConfigurationId: () => void;
  readonly onArchiveDraft: () => void;
  readonly onStartGuidedTour: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: () => void;
  readonly consoleOpen: boolean;
  readonly onToggleConsole: () => void;
  readonly consoleToggleDisabled?: boolean;
  readonly appearance: "light" | "dark";
  readonly onCloseWindow: () => void;
  readonly actionsBusy?: boolean;
}

export function WorkbenchChrome({
  configName,
  configStatus,
  workspaceLabel,
  validationLabel,
  canSaveFiles,
  isSavingFiles,
  onSaveFile,
  saveShortcutLabel,
  toggleConsoleShortcutLabel,
  onOpenActionsMenu,
  canRunValidation,
  isRunningValidation,
  onRunValidation,
  onOpenConfigurationsHome,
  onCreateConfigurationFromFileMenu,
  onCloseFromFileMenu,
  canPublish,
  isPublishing,
  onPublish,
  canRenameConfiguration,
  canArchiveDraft,
  titleMenuOpen,
  onTitleMenuOpenChange,
  onRenameConfiguration,
  onCopyConfigurationId,
  onArchiveDraft,
  onStartGuidedTour,
  canRunExtraction,
  isRunningExtraction,
  onRunExtraction,
  consoleOpen,
  onToggleConsole,
  consoleToggleDisabled = false,
  appearance,
  onCloseWindow,
  actionsBusy = false,
}: WorkbenchChromeProps) {
  const surfaceClass = "border-border bg-card text-foreground";
  const metaTextClass = "text-muted-foreground";
  const actionButtonBaseClass =
    "inline-flex h-8 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md px-3 text-[13px] font-medium leading-none shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0";
  const secondaryActionClass =
    "border border-border/80 bg-muted/15 text-foreground hover:bg-muted/35 disabled:bg-muted/20 disabled:text-muted-foreground";
  const primaryActionClass =
    "bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground";
  const { state, openMobile, isMobile, toggleSidebar } = useSidebar();
  const explorerVisible = isMobile ? openMobile : state === "expanded";
  return (
    <div className={clsx("border-b", surfaceClass)}>
      <div className="flex h-8 items-center justify-between border-b border-border/70 px-2">
        <div className="flex items-center gap-0.5">
          <WorkbenchMenu
            label="File"
            items={[
              {
                label: "Open configurations home",
                icon: <FolderOpen className="h-4 w-4" />,
                onSelect: onOpenConfigurationsHome,
              },
              {
                label: "Create new configuration",
                icon: <FilePlus2 className="h-4 w-4" />,
                onSelect: onCreateConfigurationFromFileMenu,
              },
              {
                label: "Close configuration",
                icon: <XSquare className="h-4 w-4" />,
                onSelect: onCloseFromFileMenu,
                destructive: true,
                separatorAbove: true,
              },
            ]}
          />
          <WorkbenchMenu
            label="Edit"
            items={[
              {
                label: "Rename configuration…",
                icon: <EditIcon className="h-4 w-4" />,
                onSelect: onRenameConfiguration,
                disabled: !canRenameConfiguration,
                shortcut: "F2",
              },
              {
                label: "Copy configuration ID",
                icon: <CopyIcon className="h-4 w-4" />,
                onSelect: onCopyConfigurationId,
              },
            ]}
          />
          <WorkbenchMenu
            label="View"
            items={[
              {
                label: explorerVisible ? "Hide explorer" : "Show explorer",
                icon: <SidebarIcon className="h-4 w-4" />,
                onSelect: toggleSidebar,
              },
              {
                label: consoleOpen ? "Hide console" : "Show console",
                icon: <ConsoleIcon className="h-4 w-4" />,
                onSelect: onToggleConsole,
                disabled: consoleToggleDisabled,
                shortcut: toggleConsoleShortcutLabel,
              },
            ]}
          />
          <WorkbenchMenu
            label="Run"
            items={[
              {
                label: "Save",
                icon: <SaveIcon className="h-4 w-4" />,
                onSelect: onSaveFile,
                disabled: !canSaveFiles,
                shortcut: saveShortcutLabel,
              },
              {
                label: "Run validation",
                icon: <RunIcon className="h-4 w-4" />,
                onSelect: onRunValidation,
                disabled: !canRunValidation,
              },
              {
                label: "Publish",
                icon: <RunIcon className="h-4 w-4" />,
                onSelect: onPublish,
                disabled: !canPublish,
              },
              {
                label: "Test run",
                icon: <RunIcon className="h-4 w-4" />,
                onSelect: onRunExtraction,
                disabled: !canRunExtraction,
              },
            ]}
          />
          <WorkbenchMenu
            label="Help"
            items={[
              {
                label: "Start guided tour",
                icon: <ActionsIcon className="h-4 w-4" />,
                onSelect: onStartGuidedTour,
              },
            ]}
          />
        </div>
        <div className={clsx("min-w-0 truncate px-2 text-[11px]", metaTextClass)} title={workspaceLabel}>
          Workspace · {workspaceLabel}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 px-4 py-1.5">
        <div className="flex min-w-0 items-center gap-3">
          <WorkbenchBadgeIcon />
          <div className="min-w-0">
            <ConfigurationTitleMenu
              open={titleMenuOpen}
              onOpenChange={onTitleMenuOpenChange}
              configName={configName}
              configStatus={configStatus}
              canRename={canRenameConfiguration}
              canArchiveDraft={canArchiveDraft}
              onRename={onRenameConfiguration}
              onCopyConfigurationId={onCopyConfigurationId}
              onArchiveDraft={onArchiveDraft}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
        {validationLabel ? <span className={clsx("text-xs", metaTextClass)}>{validationLabel}</span> : null}
        <button
          type="button"
          onClick={onSaveFile}
          disabled={!canSaveFiles}
          data-guided-tour="save"
          className={clsx(
            actionButtonBaseClass,
            "min-w-[6.5rem]",
            secondaryActionClass,
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
          data-guided-tour="validation"
          className={clsx(
            actionButtonBaseClass,
            secondaryActionClass,
          )}
        >
          {isRunningValidation ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          {isRunningValidation ? "Running…" : "Run validation"}
        </button>
        <button
          type="button"
          onClick={onPublish}
          disabled={!canPublish}
          data-guided-tour="publish"
          className={clsx(
            actionButtonBaseClass,
            primaryActionClass,
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
            actionButtonBaseClass,
            secondaryActionClass,
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
        <div className={clsx("flex items-center border-l pl-3", "border-border/70")}>
          <ChromeIconButton ariaLabel="Close workbench" onClick={onCloseWindow} appearance={appearance} icon={<CloseIcon className="h-3.5 w-3.5" />} />
        </div>
        </div>
      </div>
    </div>
  );
}

interface WorkbenchMenuItem {
  readonly label: string;
  readonly icon?: ReactNode;
  readonly shortcut?: string;
  readonly disabled?: boolean;
  readonly destructive?: boolean;
  readonly separatorAbove?: boolean;
  readonly onSelect: () => void;
}

function WorkbenchMenu({
  label,
  items,
}: {
  readonly label: string;
  readonly items: readonly WorkbenchMenuItem[];
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={clsx(
            "inline-flex h-6 items-center rounded px-2 text-[12px] font-medium text-muted-foreground transition",
            "hover:bg-muted/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          )}
          aria-label={`${label} menu`}
        >
          {label}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-56">
        {items.map((item) => (
          <div key={item.label}>
            {item.separatorAbove ? <DropdownMenuSeparator /> : null}
            <DropdownMenuItem
              onSelect={item.onSelect}
              disabled={item.disabled}
              variant={item.destructive ? "destructive" : "default"}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.shortcut ? (
                <span className="ml-auto text-[11px] font-medium text-muted-foreground">
                  {item.shortcut}
                </span>
              ) : null}
            </DropdownMenuItem>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
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
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-transparent text-sm transition focus-visible:outline-none focus-visible:ring-2",
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
    <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm">
      <GridIcon className="h-4 w-4" />
    </span>
  );
}
