import type { ReactNode } from "react";
import { Ellipsis } from "lucide-react";

import { ChatIcon, CloseIcon, DownloadIcon, EyeIcon, OutputIcon, RefreshIcon } from "@/components/icons";
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
  onOpenDocument,
  onOpenActivity,
  isBusy,
  onRenameRequest,
  onDeleteRequest,
  onDownloadOutput,
  onDownloadLatest,
  onDownloadVersion,
  onReprocessRequest,
  onCancelRunRequest,
}: {
  document: DocumentRow;
  onOpenDocument: () => void;
  onOpenActivity: () => void;
  isBusy: boolean;
  onRenameRequest: (document: DocumentRow) => void;
  onDeleteRequest: (document: DocumentRow) => void;
  onDownloadOutput: (document: DocumentRow) => void;
  onDownloadLatest: (document: DocumentRow) => void;
  onDownloadVersion?: (document: DocumentRow, versionNo: number) => void;
  onReprocessRequest: (document: DocumentRow) => void;
  onCancelRunRequest: (document: DocumentRow) => void;
}) {
  const isRunActive = document.lastRun?.status === "queued" || document.lastRun?.status === "running";
  const canDownloadOutput = document.lastRun?.status === "succeeded";
  const runActionLabel = isRunActive ? "Cancel run" : "Reprocess";
  const commentCount = document.commentCount ?? 0;
  const commentBadgeLabel = commentCount > 99 ? "99+" : String(commentCount);
  const latestLabel = document.currentVersionNo
    ? `Download latest (v${document.currentVersionNo})`
    : "Download latest";
  const showOriginal = typeof document.currentVersionNo === "number" && document.currentVersionNo > 1;

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
        onClick={() => (isRunActive ? onCancelRunRequest(document) : onReprocessRequest(document))}
        variant={isRunActive ? "secondary" : "ghost"}
        disabled={isBusy}
        className="shrink-0"
      >
        {isRunActive ? <CloseIcon className="h-4 w-4" /> : <RefreshIcon className="h-4 w-4" />}
      </IconButton>
      <IconButton
        label={canDownloadOutput ? "Download normalized output" : "Output not ready"}
        onClick={() => onDownloadOutput(document)}
        disabled={!canDownloadOutput}
        className="hidden shrink-0 sm:inline-flex"
      >
        <OutputIcon className="h-4 w-4" />
      </IconButton>
      <IconButton
        label={latestLabel}
        onClick={() => onDownloadLatest(document)}
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
            onSelect={() => (isRunActive ? onCancelRunRequest(document) : onReprocessRequest(document))}
            disabled={isBusy}
          >
            {runActionLabel}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => onDownloadOutput(document)}
            disabled={!canDownloadOutput}
          >
            Download normalized output
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onDownloadLatest(document)}>
            {latestLabel}
          </DropdownMenuItem>
          {showOriginal && onDownloadVersion ? (
            <DropdownMenuItem onSelect={() => onDownloadVersion(document, 1)}>
              Download original (v1)
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem onSelect={() => onRenameRequest(document)} disabled={isBusy}>
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => onDeleteRequest(document)}
            disabled={isBusy}
            className="text-destructive focus:text-destructive"
          >
            Delete
          </DropdownMenuItem>
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
