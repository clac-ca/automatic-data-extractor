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

import type { DocumentRow } from "../../../types";

export function ActionsCell({
  document,
  isPreviewOpen,
  isCommentsOpen,
  onTogglePreview,
  onToggleComments,
  isBusy,
  onDeleteRequest,
  onDownloadOutput,
  onDownloadOriginal,
}: {
  document: DocumentRow;
  isPreviewOpen: boolean;
  isCommentsOpen: boolean;
  onTogglePreview: () => void;
  onToggleComments: () => void;
  isBusy: boolean;
  onDeleteRequest: (document: DocumentRow) => void;
  onDownloadOutput: (document: DocumentRow) => void;
  onDownloadOriginal: (document: DocumentRow) => void;
}) {
  const canDownloadOutput = document.lastRun?.status === "succeeded";
  const commentCount = document.commentCount ?? 0;
  const commentBadgeLabel = commentCount > 99 ? "99+" : String(commentCount);

  return (
    <div className="flex items-center justify-end gap-2" data-ignore-row-click>
      <IconButton
        label={isPreviewOpen ? "Close preview" : "Open preview"}
        onClick={onTogglePreview}
        variant={isPreviewOpen ? "secondary" : "ghost"}
      >
        <EyeIcon className="h-4 w-4" />
      </IconButton>
      <IconButton
        label={isCommentsOpen ? "Close comments" : "Open comments"}
        onClick={onToggleComments}
        variant={isCommentsOpen ? "secondary" : "ghost"}
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
        label="Download original"
        onClick={() => onDownloadOriginal(document)}
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
