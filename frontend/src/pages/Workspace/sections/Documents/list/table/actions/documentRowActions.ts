import { createElement, type ReactNode } from "react";
import { Archive, FileText, Pencil, UserRoundPlus } from "lucide-react";

import { DownloadIcon, EyeIcon, LogsIcon } from "@/components/icons";
import type { ContextMenuItem } from "@/components/ui/context-menu-simple";

import type { DocumentRow } from "../../../shared/types";

export type DocumentRowActionSurface = "overflow" | "context";

export type DocumentRowActionDescriptor = {
  id: string;
  label: string;
  icon?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
  dividerAbove?: boolean;
  onSelect: () => void;
};

export function buildDocumentRowActions({
  document,
  lifecycle,
  isBusy,
  isSelfAssigned,
  canRenameInline,
  surface,
  onOpen,
  onOpenPreview,
  onDownloadLatest,
  onDownloadOriginal,
  onDownloadEventsLog,
  onAssignToMe,
  onRename,
  onDeleteRequest,
  onRestoreRequest,
}: {
  document: DocumentRow;
  lifecycle: "active" | "archived";
  isBusy: boolean;
  isSelfAssigned: boolean;
  canRenameInline: boolean;
  surface: DocumentRowActionSurface;
  onOpen?: () => void;
  onOpenPreview?: () => void;
  onDownloadLatest?: (document: DocumentRow) => void;
  onDownloadOriginal?: (document: DocumentRow) => void;
  onDownloadEventsLog?: (document: DocumentRow) => void;
  onAssignToMe?: () => void;
  onRename?: () => void;
  onDeleteRequest?: (document: DocumentRow) => void;
  onRestoreRequest?: (document: DocumentRow) => void;
}) {
  const actions: DocumentRowActionDescriptor[] = [];

  if (surface === "context") {
    if (onOpen) {
      actions.push({
        id: "open",
        label: "Open",
        icon: createElement(FileText, { className: "h-4 w-4" }),
        onSelect: onOpen,
      });
    }
    if (onOpenPreview) {
      actions.push({
        id: "open-preview",
        label: "Open preview",
        icon: createElement(EyeIcon, { className: "h-4 w-4" }),
        onSelect: onOpenPreview,
      });
    }
  }

  const navigationCount = actions.length;
  let appliedCoreDivider = false;
  const pushCore = (action: DocumentRowActionDescriptor) => {
    actions.push({
      ...action,
      dividerAbove: navigationCount > 0 && !appliedCoreDivider ? true : action.dividerAbove,
    });
    if (navigationCount > 0) appliedCoreDivider = true;
  };

  if (onDownloadLatest) {
    pushCore({
      id: "download",
      label: "Download",
      icon: createElement(DownloadIcon, { className: "h-4 w-4" }),
      onSelect: () => onDownloadLatest(document),
    });
  }

  if (onDownloadOriginal) {
    pushCore({
      id: "download-original",
      label: "Download original",
      icon: createElement(DownloadIcon, { className: "h-4 w-4" }),
      onSelect: () => onDownloadOriginal(document),
    });
  }

  if (surface === "overflow" && onDownloadEventsLog && document.lastRun?.id) {
    pushCore({
      id: "download-events-log",
      label: "Download events log",
      icon: createElement(LogsIcon, { className: "h-4 w-4" }),
      onSelect: () => onDownloadEventsLog(document),
    });
  }

  if (onAssignToMe && !isSelfAssigned) {
    pushCore({
      id: "assign-to-me",
      label: "Assign to me",
      icon: createElement(UserRoundPlus, { className: "h-4 w-4" }),
      disabled: isBusy,
      onSelect: onAssignToMe,
    });
  }

  if (canRenameInline && onRename) {
    pushCore({
      id: "rename",
      label: "Rename",
      icon: createElement(Pencil, { className: "h-4 w-4" }),
      disabled: isBusy,
      onSelect: onRename,
    });
  }

  if (lifecycle === "active" && onDeleteRequest) {
    pushCore({
      id: "delete",
      label: "Archive",
      icon: createElement(Archive, { className: "h-4 w-4" }),
      disabled: isBusy,
      danger: true,
      onSelect: () => onDeleteRequest(document),
    });
  }

  if (lifecycle === "archived" && onRestoreRequest) {
    pushCore({
      id: "restore",
      label: "Restore",
      disabled: isBusy,
      onSelect: () => onRestoreRequest(document),
    });
  }

  return actions;
}

export function toContextMenuItems(actions: DocumentRowActionDescriptor[]): ContextMenuItem[] {
  return actions.map((action) => ({
    id: action.id,
    label: action.label,
    icon: action.icon,
    disabled: action.disabled,
    danger: action.danger,
    dividerAbove: action.dividerAbove,
    onSelect: action.onSelect,
  }));
}
