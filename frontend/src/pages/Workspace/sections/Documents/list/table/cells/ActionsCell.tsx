import type { ReactNode } from "react";
import { Ellipsis, RotateCcw } from "lucide-react";

import { ChatIcon, CloseIcon, DownloadIcon, EyeIcon, RefreshIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { DocumentRow } from "../../../shared/types";

export function ActionsCell({
  document,
  lifecycle,
  onOpenDocument,
  onOpenActivity,
  isBusy,
  onRenameRequest,
  onDeleteRequest,
  onRestoreRequest,
  onDownload,
  onDownloadOriginal,
  onReprocessRequest,
  onCancelRunRequest,
}: {
  document: DocumentRow;
  lifecycle: "active" | "deleted";
  onOpenDocument: () => void;
  onOpenActivity: () => void;
  isBusy: boolean;
  onRenameRequest: (document: DocumentRow) => void;
  onDeleteRequest: (document: DocumentRow) => void;
  onRestoreRequest: (document: DocumentRow) => void;
  onDownload: (document: DocumentRow) => void;
  onDownloadOriginal: (document: DocumentRow) => void;
  onReprocessRequest: (document: DocumentRow) => void;
  onCancelRunRequest: (document: DocumentRow) => void;
}) {
  const isDeletedLifecycle = lifecycle === "deleted";
  const isRunActive = document.lastRun?.status === "queued" || document.lastRun?.status === "running";
  const canDownloadNormalizedOutput = document.lastRun?.status === "succeeded";
  const runActionLabel = isDeletedLifecycle ? "Restore" : isRunActive ? "Cancel run" : "Reprocess";
  const commentCount = document.commentCount ?? 0;
  const commentBadgeLabel = commentCount > 99 ? "99+" : String(commentCount);

  return (
    <div className="flex min-w-0 items-center justify-end gap-1" data-ignore-row-click>
      <IconButton
        label="Open preview"
        onClick={onOpenDocument}
        variant="ghost"
        className="shrink-0"
      >
        <EyeIcon className="h-4 w-4" />
      </IconButton>
      <IconButton
        label="Open activity"
        onClick={onOpenActivity}
        variant="ghost"
        className="relative shrink-0"
      >
        <ChatIcon className="h-4 w-4" />
        {commentCount > 0 ? (
          <span className="absolute -right-1 -top-1 min-w-[16px] rounded-full bg-primary px-1 text-[10px] font-semibold leading-4 text-primary-foreground">
            {commentBadgeLabel}
          </span>
        ) : null}
      </IconButton>
      <IconButton
        label={runActionLabel}
        onClick={() =>
          isDeletedLifecycle
            ? onRestoreRequest(document)
            : isRunActive
              ? onCancelRunRequest(document)
              : onReprocessRequest(document)
        }
        variant={isDeletedLifecycle || isRunActive ? "secondary" : "ghost"}
        disabled={isBusy}
        className="shrink-0"
      >
        {isDeletedLifecycle ? (
          <RotateCcw className="h-4 w-4" />
        ) : isRunActive ? (
          <CloseIcon className="h-4 w-4" />
        ) : (
          <RefreshIcon className="h-4 w-4" />
        )}
      </IconButton>
      <IconButton
        label={canDownloadNormalizedOutput ? "Download normalized output" : "Output not ready"}
        onClick={() => onDownload(document)}
        disabled={!canDownloadNormalizedOutput}
        className="hidden shrink-0 sm:inline-flex"
      >
        <DownloadIcon className="h-4 w-4" />
      </IconButton>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            aria-label="More actions"
            variant="ghost"
            type="button"
            className="flex size-8 shrink-0 p-0"
          >
            <Ellipsis className="size-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() =>
              isDeletedLifecycle
                ? onRestoreRequest(document)
                : isRunActive
                  ? onCancelRunRequest(document)
                  : onReprocessRequest(document)
            }
            disabled={isBusy}
          >
            {runActionLabel}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => onDownload(document)}
            disabled={!canDownloadNormalizedOutput}
          >
            Download
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onDownloadOriginal(document)}>
            Download original
          </DropdownMenuItem>
          {!isDeletedLifecycle ? (
            <DropdownMenuItem onSelect={() => onRenameRequest(document)} disabled={isBusy}>
              Rename
            </DropdownMenuItem>
          ) : null}
          {!isDeletedLifecycle ? (
            <DropdownMenuItem
              onSelect={() => onDeleteRequest(document)}
              disabled={isBusy}
              className="text-destructive focus:text-destructive"
            >
              Delete
            </DropdownMenuItem>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>
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
      className={["h-8 w-8 shrink-0", className].filter(Boolean).join(" ")}
      onClick={onClick}
      aria-label={label}
      title={label}
      disabled={disabled}
    >
      {children}
    </Button>
  );
}
