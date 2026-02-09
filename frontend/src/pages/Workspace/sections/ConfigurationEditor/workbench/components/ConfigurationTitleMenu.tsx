import clsx from "clsx";

import {
  ChevronDownSmallIcon,
  CopyIcon,
  DocumentIcon,
  EditIcon,
  TrashIcon,
} from "@/components/icons";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { normalizeConfigStatus } from "../../utils/configs";

interface ConfigurationTitleMenuProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly configName: string;
  readonly configStatus: string;
  readonly canRename: boolean;
  readonly canArchiveDraft: boolean;
  readonly onRename: () => void;
  readonly onCopyConfigurationId: () => void;
  readonly onArchiveDraft: () => void;
}

export function ConfigurationTitleMenu({
  open,
  onOpenChange,
  configName,
  configStatus,
  canRename,
  canArchiveDraft,
  onRename,
  onCopyConfigurationId,
  onArchiveDraft,
}: ConfigurationTitleMenuProps) {
  const { label, styles } = getStatusPresentation(configStatus);

  const runMenuAction = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  return (
    <DropdownMenu open={open} onOpenChange={onOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          data-guided-tour="history"
          className={clsx(
            "inline-flex h-9 min-w-0 max-w-[22rem] items-center gap-2 rounded-md border border-border/80 bg-muted/15 px-3 text-left transition",
            "hover:border-ring/40 hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          )}
          title={configName}
          aria-label={`Configuration actions for ${configName}`}
        >
          <DocumentIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 truncate text-sm font-semibold text-foreground">{configName}</span>
          <span
            className={clsx(
              "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              styles,
            )}
            aria-label={`Configuration status ${label}`}
          >
            {label}
          </span>
          <ChevronDownSmallIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80 p-1">
        <div className="border-b border-border px-2.5 py-2">
          <p className="truncate text-sm font-semibold text-foreground" title={configName}>
            {configName}
          </p>
          <p className="text-xs text-muted-foreground">Configuration actions</p>
        </div>

        <div className="px-1 py-1">
          <DropdownMenuItem disabled={!canRename} onSelect={() => runMenuAction(onRename)}>
            <EditIcon className="h-4 w-4" />
            Rename configuration…
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => runMenuAction(onCopyConfigurationId)}>
            <CopyIcon className="h-4 w-4" />
            Copy configuration ID
          </DropdownMenuItem>
          {!canRename ? (
            <p className="px-2 pb-1 text-xs text-muted-foreground">
              Rename is available for draft configurations only.
            </p>
          ) : null}
        </div>

        <DropdownMenuSeparator />

        <div className="px-1 py-1">
          <DropdownMenuItem
            disabled={!canArchiveDraft}
            onSelect={() => runMenuAction(onArchiveDraft)}
            variant="destructive"
          >
            <TrashIcon className="h-4 w-4" />
            Archive draft…
          </DropdownMenuItem>
          {!canArchiveDraft ? (
            <p className="px-2 pb-1 text-xs text-muted-foreground">
              Only draft configurations can be archived from this menu.
            </p>
          ) : null}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function getStatusPresentation(status: string): { label: string; styles: string } {
  const normalized = normalizeConfigStatus(status);
  if (normalized === "active") {
    return { label: "Active", styles: "bg-primary/10 text-primary" };
  }
  if (normalized === "draft") {
    return { label: "Draft", styles: "bg-accent text-accent-foreground" };
  }
  if (normalized === "archived") {
    return { label: "Archived", styles: "bg-secondary text-secondary-foreground" };
  }
  return { label: status || "Unknown", styles: "bg-secondary text-secondary-foreground" };
}
