import { useMemo, type ReactNode } from "react";
import { Ellipsis, Pencil, RotateCcw } from "lucide-react";

import { ChatIcon, CloseIcon, EyeIcon, RefreshIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { DocumentPresenceEntry } from "@/pages/Workspace/hooks/presence/presenceParticipants";

import type { DocumentRow } from "../../../shared/types";
import { DocumentPresenceBadges } from "../../../shared/presence/DocumentPresenceBadges";
import { buildDocumentRowActions } from "../actions/documentRowActions";

function isRunActive(document: DocumentRow) {
  return document.lastRun?.status === "queued" || document.lastRun?.status === "running";
}

export function DocumentNameCell({
  document,
  lifecycle,
  presenceEntries,
  isBusy = false,
  currentUserId,
  onOpenPreview,
  onOpenActivity,
  onRenameRequest,
  onAssignToMe,
  onDeleteRequest,
  onRestoreRequest,
  onDownloadLatest,
  onDownloadOriginal,
  onDownloadEventsLog,
  onReprocessRequest,
  onCancelRunRequest,
}: {
  document: DocumentRow;
  lifecycle: "active" | "archived";
  presenceEntries: DocumentPresenceEntry[];
  isBusy?: boolean;
  currentUserId?: string;
  onOpenPreview?: () => void;
  onOpenActivity?: () => void;
  onRenameRequest?: () => void;
  onAssignToMe?: () => void;
  onDeleteRequest?: (document: DocumentRow) => void;
  onRestoreRequest?: (document: DocumentRow) => void;
  onDownloadLatest?: (document: DocumentRow) => void;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onDownloadEventsLog?: (document: DocumentRow) => void;
  onReprocessRequest?: (document: DocumentRow) => void;
  onCancelRunRequest?: (document: DocumentRow) => void;
}) {
  const isArchivedLifecycle = lifecycle === "archived";
  const runActive = isRunActive(document);
  const runActionLabel = isArchivedLifecycle ? "Restore" : runActive ? "Cancel run" : "Reprocess";
  const commentCount = document.commentCount ?? 0;
  const commentBadgeLabel = commentCount > 99 ? "99+" : String(commentCount);
  const isSelfAssigned = Boolean(currentUserId && document.assignee?.id === currentUserId);
  const canRename = Boolean(onRenameRequest);

  const runActionIcon = useMemo(() => {
    if (isArchivedLifecycle) return <RotateCcw className="h-4 w-4" />;
    if (runActive) return <CloseIcon className="h-4 w-4" />;
    return <RefreshIcon className="h-4 w-4" />;
  }, [isArchivedLifecycle, runActive]);

  const overflowActions = useMemo(
    () =>
      buildDocumentRowActions({
        document,
        lifecycle,
        isBusy,
        isSelfAssigned,
        surface: "overflow",
        onDownloadLatest,
        onDownloadOriginal,
        onDownloadEventsLog,
        onAssignToMe,
        onRename: onRenameRequest,
        onDeleteRequest,
        onRestoreRequest,
      }),
    [
      document,
      isBusy,
      isSelfAssigned,
      lifecycle,
      onAssignToMe,
      onDeleteRequest,
      onDownloadLatest,
      onDownloadOriginal,
      onDownloadEventsLog,
      onRenameRequest,
      onRestoreRequest,
    ],
  );

  return (
    <div className="group/name-cell flex min-w-0 items-start gap-2">
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium" title={document.name}>
          {document.name}
        </div>
        <DocumentPresenceBadges entries={presenceEntries} />
      </div>

      <div
        className="flex shrink-0 items-center gap-1 opacity-100 md:opacity-0 md:group-hover/name-cell:opacity-100 md:group-focus-within/name-cell:opacity-100"
        data-row-interactive
        data-ignore-row-click
      >
        {canRename ? (
          <IconButton
            label="Rename document"
            onClick={() => onRenameRequest?.()}
            disabled={isBusy}
          >
            <Pencil className="h-4 w-4" />
          </IconButton>
        ) : null}
        {onOpenPreview ? (
          <IconButton label="Open preview" onClick={onOpenPreview}>
            <EyeIcon className="h-4 w-4" />
          </IconButton>
        ) : null}
        {onOpenActivity ? (
          <IconButton label="Open activity" onClick={onOpenActivity} className="relative">
            <ChatIcon className="h-4 w-4" />
            {commentCount > 0 ? (
              <span className="absolute -right-1 -top-1 min-w-[16px] rounded-full bg-primary px-1 text-[10px] font-semibold leading-4 text-primary-foreground">
                {commentBadgeLabel}
              </span>
            ) : null}
          </IconButton>
        ) : null}
        <IconButton
          label={runActionLabel}
          onClick={() => {
            if (isArchivedLifecycle) {
              onRestoreRequest?.(document);
              return;
            }
            if (runActive) {
              onCancelRunRequest?.(document);
              return;
            }
            onReprocessRequest?.(document);
          }}
          variant={isArchivedLifecycle || runActive ? "secondary" : "ghost"}
          disabled={isBusy}
        >
          {runActionIcon}
        </IconButton>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              aria-label="More actions"
              variant="ghost"
              type="button"
              className="flex h-8 w-8 shrink-0 p-0"
              data-row-interactive
            >
              <Ellipsis className="h-4 w-4" aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" data-row-interactive>
            {overflowActions.map((action) => (
              <DropdownMenuItem
                key={action.id}
                onSelect={action.onSelect}
                disabled={action.disabled}
                className={cn(
                  action.dividerAbove && "mt-1 border-border/60 border-t pt-1",
                  action.danger && "text-destructive focus:text-destructive",
                )}
              >
                {action.icon ? (
                  <span className="mr-2 inline-flex items-center text-muted-foreground">{action.icon}</span>
                ) : null}
                {action.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children,
  variant = "ghost",
  disabled = false,
  className,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  variant?: "ghost" | "secondary";
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Button
      type="button"
      variant={variant}
      size="icon"
      className={cn("h-8 w-8 shrink-0", className)}
      onClick={onClick}
      aria-label={label}
      title={label}
      disabled={disabled}
      data-row-interactive
    >
      {children}
    </Button>
  );
}
