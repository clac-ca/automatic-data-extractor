import { useState } from "react";

import { ContextMenu } from "@ui/ContextMenu";

import { DownloadIcon, LinkIcon, MoreIcon } from "./icons";

export function RowActionsMenu({
  onDownloadOutput,
  onDownloadOriginal,
  onCopyLink,
  outputDisabled,
  originalDisabled,
  copyDisabled,
}: {
  onDownloadOutput: () => void;
  onDownloadOriginal: () => void;
  onCopyLink: () => void;
  outputDisabled?: boolean;
  originalDisabled?: boolean;
  copyDisabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);

  return (
    <>
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition hover:bg-background"
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
            id: "download-output",
            label: "Download output",
            onSelect: onDownloadOutput,
            disabled: outputDisabled,
            icon: <DownloadIcon className="h-4 w-4" />,
          },
          {
            id: "download-original",
            label: "Download original",
            onSelect: onDownloadOriginal,
            disabled: originalDisabled,
            icon: <DownloadIcon className="h-4 w-4" />,
          },
          {
            id: "copy-link",
            label: "Copy link",
            onSelect: onCopyLink,
            disabled: copyDisabled,
            icon: <LinkIcon className="h-4 w-4" />,
            dividerAbove: true,
          },
        ]}
      />
    </>
  );
}
