import type { ReactNode } from "react";
import { Ellipsis } from "lucide-react";

import { ChatIcon, DownloadIcon, EyeIcon, OutputIcon } from "@/components/icons";
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
}) {
  const canDownloadOutput = document.lastRun?.status === "succeeded";
  const commentCount = document.commentCount ?? 0;
  const commentBadgeLabel = commentCount > 99 ? "99+" : String(commentCount);
  const latestLabel = document.currentVersionNo
    ? `Download latest (v${document.currentVersionNo})`
    : "Download latest";
  const showOriginal = typeof document.currentVersionNo === "number" && document.currentVersionNo > 1;

  return (
    <div className="flex items-center justify-end gap-2" data-ignore-row-click>
      <IconButton
        label="Open preview"
        onClick={onOpenDocument}
        variant="ghost"
      >
        <EyeIcon className="h-4 w-4" />
      </IconButton>
      <IconButton
        label="Open activity"
        onClick={onOpenActivity}
        variant="ghost"
        className="relative"
      >
        <ChatIcon className="h-4 w-4" />
        {commentCount > 0 ? (
          <span className="absolute -right-1 -top-1 min-w-[16px] rounded-full bg-primary px-1 text-[10px] font-semibold leading-4 text-primary-foreground">
            {commentBadgeLabel}
          </span>
        ) : null}
      </IconButton>
      <IconButton
        label={canDownloadOutput ? "Download normalized output" : "Output not ready"}
        onClick={() => onDownloadOutput(document)}
        disabled={!canDownloadOutput}
      >
        <OutputIcon className="h-4 w-4" />
      </IconButton>
      <IconButton
        label={latestLabel}
        onClick={() => onDownloadLatest(document)}
      >
        <DownloadIcon className="h-4 w-4" />
      </IconButton>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            aria-label="More actions"
            variant="ghost"
            type="button"
            className="flex size-8 p-0"
          >
            <Ellipsis className="size-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
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
      className={["h-8 w-8", className].filter(Boolean).join(" ")}
      onClick={onClick}
      aria-label={label}
      title={label}
      disabled={disabled}
    >
      {children}
    </Button>
  );
}
