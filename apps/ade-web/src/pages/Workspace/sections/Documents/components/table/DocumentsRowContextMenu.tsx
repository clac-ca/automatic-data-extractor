import type { ReactNode } from "react";

import {
  ContextMenu,
  ContextMenuCheckboxItem,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuLabel,
  ContextMenuRadioGroup,
  ContextMenuRadioItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuTrigger,
} from "@@/components/components@/components/ui@/components/context-menu";
import {
  ChatIcon,
  CopyIcon,
  DownloadIcon,
  EyeIcon,
  OutputIcon,
  TagIcon,
  TrashIcon,
  UserIcon,
} from "@components@/components/icons";

import type { DocumentRow, WorkspacePerson } from "..@/components/..@/components/types";

const MENU_ICON_CLASS = "h-4 w-4";

export function DocumentsRowContextMenu({
  document,
  people,
  tagOptions,
  isPreviewOpen,
  isCommentsOpen,
  onTogglePreview,
  onToggleComments,
  onAssign,
  onToggleTag,
  onDownloadOutput,
  onDownloadOriginal,
  onDeleteRequest,
  isBusy,
  children,
}: {
  readonly document: DocumentRow;
  readonly people: WorkspacePerson[];
  readonly tagOptions: string[];
  readonly isPreviewOpen: boolean;
  readonly isCommentsOpen: boolean;
  readonly onTogglePreview: (documentId: string) => void;
  readonly onToggleComments: (documentId: string) => void;
  readonly onAssign: (documentId: string, assigneeId: string | null) => void;
  readonly onToggleTag: (documentId: string, tag: string) => void;
  readonly onDownloadOutput: (document: DocumentRow) => void;
  readonly onDownloadOriginal: (document: DocumentRow) => void;
  readonly onDeleteRequest: (document: DocumentRow) => void;
  readonly isBusy: boolean;
  readonly children: ReactNode;
}) {
  const canDownloadOutput = Boolean(document.lastSuccessfulRun?.id);
  const outputLabel = canDownloadOutput ? "Download output" : "Output not ready";
  const previewLabel = isPreviewOpen ? "Close preview" : "Open preview";
  const commentsLabel = isCommentsOpen ? "Close comments" : "Open comments";
  const assigneeValue = document.assignee?.id ?? "unassigned";
  const selectedTags = new Set(document.tags ?? []);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}<@/components/ContextMenuTrigger>
      <ContextMenuContent className="w-64">
        <ContextMenuLabel className="max-w-[240px] truncate" title={document.name}>
          {document.name}
        <@/components/ContextMenuLabel>
        <ContextMenuSeparator @/components/>
        <ContextMenuItem onSelect={() => onTogglePreview(document.id)}>
          <EyeIcon className={MENU_ICON_CLASS} @/components/>
          <span className="flex-1">{previewLabel}<@/components/span>
        <@/components/ContextMenuItem>
        <ContextMenuItem onSelect={() => onToggleComments(document.id)}>
          <ChatIcon className={MENU_ICON_CLASS} @/components/>
          <span className="flex-1">{commentsLabel}<@/components/span>
        <@/components/ContextMenuItem>
        <ContextMenuSeparator @/components/>
        <ContextMenuItem disabled={!canDownloadOutput} onSelect={() => onDownloadOutput(document)}>
          <OutputIcon className={MENU_ICON_CLASS} @/components/>
          <span className="flex-1">{outputLabel}<@/components/span>
        <@/components/ContextMenuItem>
        <ContextMenuItem onSelect={() => onDownloadOriginal(document)}>
          <DownloadIcon className={MENU_ICON_CLASS} @/components/>
          <span className="flex-1">Download original<@/components/span>
        <@/components/ContextMenuItem>
        <ContextMenuSeparator @/components/>
        <ContextMenuSub>
          <ContextMenuSubTrigger className="gap-2">
            <UserIcon className={MENU_ICON_CLASS} @/components/>
            <span className="flex-1">Assignee<@/components/span>
          <@/components/ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-56 max-h-72 overflow-y-auto overflow-x-hidden">
            <ContextMenuRadioGroup
              value={assigneeValue}
              onValueChange={(value) => onAssign(document.id, value === "unassigned" ? null : value)}
            >
              <ContextMenuRadioItem value="unassigned" disabled={isBusy}>
                Unassigned
              <@/components/ContextMenuRadioItem>
              {people.map((person) => (
                <ContextMenuRadioItem key={person.id} value={person.id} disabled={isBusy}>
                  {person.label}
                <@/components/ContextMenuRadioItem>
              ))}
            <@/components/ContextMenuRadioGroup>
          <@/components/ContextMenuSubContent>
        <@/components/ContextMenuSub>
        <ContextMenuSub>
          <ContextMenuSubTrigger className="gap-2">
            <TagIcon className={MENU_ICON_CLASS} @/components/>
            <span className="flex-1">Tags<@/components/span>
          <@/components/ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-56 max-h-72 overflow-y-auto overflow-x-hidden">
            {tagOptions.length === 0 ? (
              <ContextMenuItem disabled>No tags available<@/components/ContextMenuItem>
            ) : (
              tagOptions.map((tag) => (
                <ContextMenuCheckboxItem
                  key={tag}
                  checked={selectedTags.has(tag)}
                  onSelect={(event) => event.preventDefault()}
                  onCheckedChange={() => onToggleTag(document.id, tag)}
                  disabled={isBusy}
                >
                  {tag}
                <@/components/ContextMenuCheckboxItem>
              ))
            )}
          <@/components/ContextMenuSubContent>
        <@/components/ContextMenuSub>
        <ContextMenuSub>
          <ContextMenuSubTrigger className="gap-2">
            <CopyIcon className={MENU_ICON_CLASS} @/components/>
            <span className="flex-1">Copy<@/components/span>
          <@/components/ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-52">
            <ContextMenuItem
              onSelect={() => {
                void copyText(document.name);
              }}
            >
              Copy name
            <@/components/ContextMenuItem>
            <ContextMenuItem
              onSelect={() => {
                void copyText(document.id);
              }}
            >
              Copy ID
            <@/components/ContextMenuItem>
          <@/components/ContextMenuSubContent>
        <@/components/ContextMenuSub>
        <ContextMenuSeparator @/components/>
        <ContextMenuItem
          variant="destructive"
          onSelect={() => onDeleteRequest(document)}
          disabled={isBusy}
        >
          <TrashIcon className={MENU_ICON_CLASS} @/components/>
          <span className="flex-1">Delete document<@/components/span>
        <@/components/ContextMenuItem>
      <@/components/ContextMenuContent>
    <@/components/ContextMenu>
  );
}

async function copyText(value: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      @/components/@/components/ fall through to manual copy
    }
  }
  if (typeof document === "undefined") {
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}
