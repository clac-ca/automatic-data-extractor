import { Ellipsis } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { DocumentRow } from "../../../types";

export function ActionsCell({
  document,
  isBusy,
  onArchive,
  onRestore,
  onDeleteRequest,
  onDownloadOutput,
  onDownloadOriginal,
}: {
  document: DocumentRow;
  isBusy: boolean;
  onArchive: (documentId: string) => void;
  onRestore: (documentId: string) => void;
  onDeleteRequest: (document: DocumentRow) => void;
  onDownloadOutput: (document: DocumentRow) => void;
  onDownloadOriginal: (document: DocumentRow) => void;
}) {
  const canDownloadOutput = Boolean(document.latestSuccessfulRun?.id);
  const isArchived = document.status === "archived";

  return (
    <div className="flex justify-end" data-ignore-row-click>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            aria-label="Open menu"
            variant="ghost"
            type="button"
            className="flex size-8 p-0"
          >
            <Ellipsis className="size-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => onDownloadOutput(document)}
            disabled={!canDownloadOutput}
          >
            Download normalized
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onDownloadOriginal(document)}>
            Download original
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {isArchived ? (
            <DropdownMenuItem
              onSelect={() => onRestore(document.id)}
              disabled={isBusy}
            >
              Restore
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem
              onSelect={() => onArchive(document.id)}
              disabled={isBusy}
            >
              Archive
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
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
