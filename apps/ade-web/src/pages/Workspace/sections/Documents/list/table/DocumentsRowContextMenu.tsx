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
} from "@/components/ui/context-menu";
import {
  ChatIcon,
  CopyIcon,
  DownloadIcon,
  EyeIcon,
  OutputIcon,
  TagIcon,
  TrashIcon,
  UserIcon,
} from "@/components/icons";

import type { DocumentRow, WorkspacePerson } from "../../shared/types";

const MENU_ICON_CLASS = "h-4 w-4";

export function DocumentsRowContextMenu({
  document,
  people,
  tagOptions,
  onOpenDocument,
  onOpenComments,
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
  readonly onOpenDocument: (documentId: string) => void;
  readonly onOpenComments: (documentId: string) => void;
  readonly onAssign: (documentId: string, assigneeId: string | null) => void;
  readonly onToggleTag: (documentId: string, tag: string) => void;
  readonly onDownloadOutput: (document: DocumentRow) => void;
  readonly onDownloadOriginal: (document: DocumentRow) => void;
  readonly onDeleteRequest: (document: DocumentRow) => void;
  readonly isBusy: boolean;
  readonly children: ReactNode;
}) {
  const canDownloadOutput = document.lastRun?.status === "succeeded";
  const outputLabel = canDownloadOutput ? "Download output" : "Output not ready";
  const assigneeValue = document.assignee?.id ?? "unassigned";
  const selectedTags = new Set(document.tags ?? []);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-64">
        <ContextMenuLabel className="max-w-[240px] truncate" title={document.name}>
          {document.name}
        </ContextMenuLabel>
        <ContextMenuSeparator />
        <ContextMenuItem onSelect={() => onOpenDocument(document.id)}>
          <EyeIcon className={MENU_ICON_CLASS} />
          <span className="flex-1">Open document</span>
        </ContextMenuItem>
        <ContextMenuItem onSelect={() => onOpenComments(document.id)}>
          <ChatIcon className={MENU_ICON_CLASS} />
          <span className="flex-1">Open comments</span>
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuItem disabled={!canDownloadOutput} onSelect={() => onDownloadOutput(document)}>
          <OutputIcon className={MENU_ICON_CLASS} />
          <span className="flex-1">{outputLabel}</span>
        </ContextMenuItem>
        <ContextMenuItem onSelect={() => onDownloadOriginal(document)}>
          <DownloadIcon className={MENU_ICON_CLASS} />
          <span className="flex-1">Download original</span>
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuSub>
          <ContextMenuSubTrigger className="gap-2">
            <UserIcon className={MENU_ICON_CLASS} />
            <span className="flex-1">Assignee</span>
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-56 max-h-72 overflow-y-auto overflow-x-hidden">
            <ContextMenuRadioGroup
              value={assigneeValue}
              onValueChange={(value) => onAssign(document.id, value === "unassigned" ? null : value)}
            >
              <ContextMenuRadioItem value="unassigned" disabled={isBusy}>
                Unassigned
              </ContextMenuRadioItem>
              {people.map((person) => (
                <ContextMenuRadioItem key={person.id} value={person.id} disabled={isBusy}>
                  {person.label}
                </ContextMenuRadioItem>
              ))}
            </ContextMenuRadioGroup>
          </ContextMenuSubContent>
        </ContextMenuSub>
        <ContextMenuSub>
          <ContextMenuSubTrigger className="gap-2">
            <TagIcon className={MENU_ICON_CLASS} />
            <span className="flex-1">Tags</span>
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-56 max-h-72 overflow-y-auto overflow-x-hidden">
            {tagOptions.length === 0 ? (
              <ContextMenuItem disabled>No tags available</ContextMenuItem>
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
                </ContextMenuCheckboxItem>
              ))
            )}
          </ContextMenuSubContent>
        </ContextMenuSub>
        <ContextMenuSub>
          <ContextMenuSubTrigger className="gap-2">
            <CopyIcon className={MENU_ICON_CLASS} />
            <span className="flex-1">Copy</span>
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-52">
            <ContextMenuItem
              onSelect={() => {
                void copyText(document.name);
              }}
            >
              Copy name
            </ContextMenuItem>
            <ContextMenuItem
              onSelect={() => {
                void copyText(document.id);
              }}
            >
              Copy ID
            </ContextMenuItem>
          </ContextMenuSubContent>
        </ContextMenuSub>
        <ContextMenuSeparator />
        <ContextMenuItem
          variant="destructive"
          onSelect={() => onDeleteRequest(document)}
          disabled={isBusy}
        >
          <TrashIcon className={MENU_ICON_CLASS} />
          <span className="flex-1">Delete document</span>
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}

async function copyText(value: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall through to manual copy.
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
