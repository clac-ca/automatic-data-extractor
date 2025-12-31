import { useState } from "react";

import { ContextMenu, type ContextMenuItem } from "@components/ContextMenu";

import {
  CloseIcon,
  DownloadIcon,
  FolderMinusIcon,
  FolderOpenIcon,
  LinkIcon,
  MoreIcon,
  RefreshIcon,
  TrashIcon,
} from "@components/Icons";

export function RowActionsMenu({
  onOpenDetails,
  onReprocess,
  reprocessDisabled,
  showClosePreview,
  onClosePreview,
  onDownloadOriginal,
  onCopyLink,
  onDelete,
  onArchive,
  onRestore,
  isArchived,
  originalDisabled,
  copyDisabled,
  deleteDisabled,
  archiveDisabled,
}: {
  onOpenDetails: () => void;
  onReprocess?: () => void;
  reprocessDisabled?: boolean;
  showClosePreview?: boolean;
  onClosePreview?: () => void;
  onDownloadOriginal: () => void;
  onCopyLink: () => void;
  onDelete?: () => void;
  onArchive?: () => void;
  onRestore?: () => void;
  isArchived?: boolean;
  originalDisabled?: boolean;
  copyDisabled?: boolean;
  deleteDisabled?: boolean;
  archiveDisabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const showArchive = Boolean(onArchive) && !isArchived;
  const showRestore = Boolean(onRestore) && Boolean(isArchived);
  const hasArchiveAction = showArchive || showRestore;
  const items: ContextMenuItem[] = [
    {
      id: "details",
      label: "Open details",
      onSelect: onOpenDetails,
    },
  ];

  if (onReprocess) {
    items.push({
      id: "reprocess",
      label: "Reprocess",
      onSelect: onReprocess,
      disabled: reprocessDisabled,
      icon: <RefreshIcon className="h-4 w-4" />,
    });
  }

  items.push({
    id: "download-original",
    label: "Download original",
    onSelect: onDownloadOriginal,
    disabled: originalDisabled,
    icon: <DownloadIcon className="h-4 w-4" />,
    dividerAbove: true,
  });

  items.push({
    id: "copy-link",
    label: "Copy link",
    onSelect: onCopyLink,
    disabled: copyDisabled,
    icon: <LinkIcon className="h-4 w-4" />,
  });

  if (showArchive && onArchive) {
    items.push({
      id: "archive",
      label: "Archive document",
      onSelect: onArchive,
      disabled: archiveDisabled,
      icon: <FolderMinusIcon className="h-4 w-4" />,
      dividerAbove: true,
    });
  }

  if (showRestore && onRestore) {
    items.push({
      id: "restore",
      label: "Restore document",
      onSelect: onRestore,
      disabled: archiveDisabled,
      icon: <FolderOpenIcon className="h-4 w-4" />,
      dividerAbove: true,
    });
  }

  if (showClosePreview && onClosePreview) {
    items.push({
      id: "close-preview",
      label: "Close preview",
      onSelect: onClosePreview,
      icon: <CloseIcon className="h-4 w-4" />,
      dividerAbove: !onDelete,
    });
  }

  if (onDelete) {
    items.push({
      id: "delete",
      label: "Delete document",
      onSelect: onDelete,
      disabled: deleteDisabled,
      danger: true,
      icon: <TrashIcon className="h-4 w-4" />,
      dividerAbove: !hasArchiveAction,
    });
  }

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
        items={items}
      />
    </>
  );
}
