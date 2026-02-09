import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Check, Ellipsis, Pencil, RotateCcw, X } from "lucide-react";

import { ChatIcon, CloseIcon, EyeIcon, RefreshIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { DocumentPresenceEntry } from "@/pages/Workspace/hooks/presence/presenceParticipants";
import {
  composeFileName,
  splitFileName,
} from "@/pages/Workspace/sections/Documents/shared/rename/fileNameParts";

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
  onRename,
  onAssignToMe,
  onDeleteRequest,
  onRestoreRequest,
  onDownloadLatest,
  onDownloadOriginal,
  onReprocessRequest,
  onCancelRunRequest,
  externalRenameSignal,
}: {
  document: DocumentRow;
  lifecycle: "active" | "deleted";
  presenceEntries: DocumentPresenceEntry[];
  isBusy?: boolean;
  currentUserId?: string;
  onOpenPreview?: () => void;
  onOpenActivity?: () => void;
  onRename?: (nextName: string) => Promise<void> | void;
  onAssignToMe?: () => void;
  onDeleteRequest?: (document: DocumentRow) => void;
  onRestoreRequest?: (document: DocumentRow) => void;
  onDownloadLatest?: (document: DocumentRow) => void;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onReprocessRequest?: (document: DocumentRow) => void;
  onCancelRunRequest?: (document: DocumentRow) => void;
  externalRenameSignal?: number;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftBaseName, setDraftBaseName] = useState(() => splitFileName(document.name).baseName);
  const [lockedExtension, setLockedExtension] = useState(() => splitFileName(document.name).extension);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [isSubmittingRename, setIsSubmittingRename] = useState(false);
  const lastRenameSignalRef = useRef(externalRenameSignal ?? 0);

  const isDeletedLifecycle = lifecycle === "deleted";
  const runActive = isRunActive(document);
  const runActionLabel = isDeletedLifecycle ? "Restore" : runActive ? "Cancel run" : "Reprocess";
  const commentCount = document.commentCount ?? 0;
  const commentBadgeLabel = commentCount > 99 ? "99+" : String(commentCount);
  const isSelfAssigned = Boolean(currentUserId && document.assignee?.id === currentUserId);

  const canRenameInline = Boolean(onRename && !isDeletedLifecycle);
  const resetDraftFromName = useCallback((name: string) => {
    const next = splitFileName(name);
    setDraftBaseName(next.baseName);
    setLockedExtension(next.extension);
  }, []);

  const startRename = useCallback(() => {
    if (!canRenameInline || isBusy) return;
    resetDraftFromName(document.name);
    setIsEditing(true);
    setRenameError(null);
  }, [canRenameInline, document.name, isBusy, resetDraftFromName]);

  useEffect(() => {
    if (isEditing) return;
    resetDraftFromName(document.name);
  }, [document.name, isEditing, resetDraftFromName]);

  const submitRename = async () => {
    if (!onRename) return;
    const normalizedBase = draftBaseName.trim();
    if (!normalizedBase) {
      setRenameError("Document name cannot be blank.");
      return;
    }
    const nextName = composeFileName({
      baseName: normalizedBase,
      extension: lockedExtension,
    });
    if (nextName === document.name) {
      setIsEditing(false);
      setRenameError(null);
      return;
    }

    setIsSubmittingRename(true);
    setRenameError(null);
    try {
      await onRename(nextName);
      setIsEditing(false);
      setRenameError(null);
    } catch (error) {
      setRenameError(error instanceof Error ? error.message : "Unable to rename document.");
    } finally {
      setIsSubmittingRename(false);
    }
  };

  const runActionIcon = useMemo(() => {
    if (isDeletedLifecycle) return <RotateCcw className="h-4 w-4" />;
    if (runActive) return <CloseIcon className="h-4 w-4" />;
    return <RefreshIcon className="h-4 w-4" />;
  }, [isDeletedLifecycle, runActive]);

  useEffect(() => {
    const nextSignal = externalRenameSignal ?? 0;
    if (nextSignal === lastRenameSignalRef.current) return;
    lastRenameSignalRef.current = nextSignal;
    startRename();
  }, [externalRenameSignal, startRename]);

  const overflowActions = useMemo(
    () =>
      buildDocumentRowActions({
        document,
        lifecycle,
        isBusy,
        isSelfAssigned,
        canRenameInline,
        surface: "overflow",
        onDownloadLatest,
        onDownloadOriginal,
        onAssignToMe,
        onRename: startRename,
        onDeleteRequest,
      }),
    [
      canRenameInline,
      document,
      isBusy,
      isSelfAssigned,
      lifecycle,
      onAssignToMe,
      onDeleteRequest,
      onDownloadLatest,
      onDownloadOriginal,
      startRename,
    ],
  );

  return (
    <div className="group/name-cell flex min-w-0 items-start gap-2">
      <div className="min-w-0 flex-1">
        {isEditing ? (
          <div className="space-y-1" data-row-interactive data-ignore-row-click>
            <div className="flex items-center gap-1">
              <Input
                value={draftBaseName}
                onChange={(event) => setDraftBaseName(event.target.value)}
                autoFocus
                disabled={isSubmittingRename || isBusy}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void submitRename();
                  }
                  if (event.key === "Escape") {
                    event.preventDefault();
                    resetDraftFromName(document.name);
                    setIsEditing(false);
                    setRenameError(null);
                  }
                }}
                className={lockedExtension ? "h-8 rounded-r-none border-r-0" : "h-8"}
              />
              {lockedExtension ? (
                <div className="inline-flex h-8 items-center rounded-r-md border border-input bg-muted/40 px-2 text-xs text-muted-foreground">
                  {lockedExtension}
                </div>
              ) : null}
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={() => {
                  void submitRename();
                }}
                disabled={isSubmittingRename || isBusy}
                aria-label="Save document name"
                data-row-interactive
              >
                <Check className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={() => {
                  resetDraftFromName(document.name);
                  setIsEditing(false);
                  setRenameError(null);
                }}
                disabled={isSubmittingRename || isBusy}
                aria-label="Cancel rename"
                data-row-interactive
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            {renameError ? <p className="text-xs text-destructive">{renameError}</p> : null}
          </div>
        ) : (
          <>
            {canRenameInline ? (
              <button
                type="button"
                data-allow-row-activate
                className="w-full truncate text-left font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                title={document.name}
                onDoubleClick={() => {
                  startRename();
                }}
                onKeyDown={(event) => {
                  if (event.key !== "F2") return;
                  event.preventDefault();
                  startRename();
                }}
              >
                {document.name}
              </button>
            ) : (
              <div className="truncate font-medium" title={document.name}>
                {document.name}
              </div>
            )}
          </>
        )}
        <DocumentPresenceBadges entries={presenceEntries} />
      </div>

      <div
        className="flex shrink-0 items-center gap-1 opacity-100 md:opacity-0 md:group-hover/name-cell:opacity-100 md:group-focus-within/name-cell:opacity-100"
        data-row-interactive
        data-ignore-row-click
      >
        {canRenameInline ? (
          <IconButton
            label="Rename document"
            onClick={startRename}
            disabled={isSubmittingRename || isBusy}
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
            if (isDeletedLifecycle) {
              onRestoreRequest?.(document);
              return;
            }
            if (runActive) {
              onCancelRunRequest?.(document);
              return;
            }
            onReprocessRequest?.(document);
          }}
          variant={isDeletedLifecycle || runActive ? "secondary" : "ghost"}
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
