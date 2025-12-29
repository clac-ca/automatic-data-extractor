import { useState } from "react";

import { ContextMenu } from "@ui/ContextMenu";

import { CloseIcon, DownloadIcon, LinkIcon, MoreIcon, RefreshIcon } from "./icons";

export function RowActionsMenu({
  onOpenDetails,
  onReprocess,
  reprocessDisabled,
  showClosePreview,
  onClosePreview,
  onDownloadOriginal,
  onCopyLink,
  originalDisabled,
  copyDisabled,
}: {
  onOpenDetails: () => void;
  onReprocess?: () => void;
  reprocessDisabled?: boolean;
  showClosePreview?: boolean;
  onClosePreview?: () => void;
  onDownloadOriginal: () => void;
  onCopyLink: () => void;
  originalDisabled?: boolean;
  copyDisabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);

  return (
    <>
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent bg-transparent text-muted-foreground transition hover:border-border hover:bg-background hover:text-muted-foreground"
        onClick={(event) => {
          event.stopPropagation();
          setPosition({ x: event.clientX, y: event.clientY });
          setOpen(true);
        }}
        aria-label="Row actions"
      >
        <MoreIcon className="h-4 w-4" />
      </button>

      <ContextMenu
        open={open}
        position={position}
        onClose={() => setOpen(false)}
        appearance="light"
        items={[
          {
            id: "details",
            label: "Open details",
            onSelect: onOpenDetails,
          },
          ...(onReprocess
            ? [
                {
                  id: "reprocess",
                  label: "Reprocess",
                  onSelect: onReprocess,
                  disabled: reprocessDisabled,
                  icon: <RefreshIcon className="h-4 w-4" />,
                },
              ]
            : []),
          {
            id: "download-original",
            label: "Download original",
            onSelect: onDownloadOriginal,
            disabled: originalDisabled,
            icon: <DownloadIcon className="h-4 w-4" />,
            dividerAbove: true,
          },
          {
            id: "copy-link",
            label: "Copy link",
            onSelect: onCopyLink,
            disabled: copyDisabled,
            icon: <LinkIcon className="h-4 w-4" />,
          },
          ...(showClosePreview && onClosePreview
            ? [
                {
                  id: "close-preview",
                  label: "Close preview",
                  onSelect: onClosePreview,
                  icon: <CloseIcon className="h-4 w-4" />,
                  dividerAbove: true,
                },
              ]
            : []),
        ]}
      />
    </>
  );
}
