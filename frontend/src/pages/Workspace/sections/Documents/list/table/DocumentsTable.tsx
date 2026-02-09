import { useEffect, useState, type ReactNode } from "react";
import { type Table } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { DataTableViewOptions } from "@/components/data-table/data-table-view-options";
import { ContextMenu, type ContextMenuItem } from "@/components/ui/context-menu-simple";
import {
  ActionBar,
  ActionBarGroup,
  ActionBarItem,
  ActionBarSelection,
  ActionBarSeparator,
} from "@/components/ui/action-bar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useIsMobile } from "@/hooks/use-mobile";
import type { DocumentPresenceEntry } from "@/pages/Workspace/hooks/presence/presenceParticipants";
import type { DocumentRow } from "../../shared/types";
import { DocumentsActiveFiltersRail } from "./DocumentsActiveFiltersRail";
import { DocumentsMobileCard } from "./DocumentsMobileCard";

interface DocumentsTableProps {
  table: Table<DocumentRow>;
  debounceMs: number;
  throttleMs: number;
  shallow: boolean;
  rowPresence?: Map<string, DocumentPresenceEntry[]>;
  leadingToolbarActions?: ReactNode;
  toolbarActions?: ReactNode;
  onRowActivate?: (document: DocumentRow) => void;
  onBulkReprocessRequest?: (documents: DocumentRow[]) => void;
  onBulkCancelRequest?: (documents: DocumentRow[]) => void;
  onBulkAssignRequest?: (documents: DocumentRow[]) => void;
  onBulkTagRequest?: (documents: DocumentRow[]) => void;
  onBulkDeleteRequest?: (documents: DocumentRow[]) => void;
  onBulkRestoreRequest?: (documents: DocumentRow[]) => void;
  onBulkDownloadRequest?: (documents: DocumentRow[]) => void;
  onBulkDownloadOriginalRequest?: (documents: DocumentRow[]) => void;
  buildRowContextMenuItems?: (document: DocumentRow) => ContextMenuItem[];
  selectionResetToken?: number;
}

export function DocumentsTable({
  table,
  debounceMs,
  throttleMs,
  shallow,
  rowPresence,
  leadingToolbarActions,
  toolbarActions,
  onRowActivate,
  onBulkReprocessRequest,
  onBulkCancelRequest,
  onBulkAssignRequest,
  onBulkTagRequest,
  onBulkDeleteRequest,
  onBulkRestoreRequest,
  onBulkDownloadRequest,
  onBulkDownloadOriginalRequest,
  buildRowContextMenuItems,
  selectionResetToken = 0,
}: DocumentsTableProps) {
  const isMobile = useIsMobile();
  const [rowContextMenu, setRowContextMenu] = useState<{
    position: { x: number; y: number };
    items: ContextMenuItem[];
  } | null>(null);

  useEffect(() => {
    table.toggleAllRowsSelected(false);
  }, [selectionResetToken, table]);

  useEffect(() => {
    if (isMobile && rowContextMenu) {
      setRowContextMenu(null);
    }
  }, [isMobile, rowContextMenu]);

  const selectedRows = table.getFilteredSelectedRowModel().rows;
  const selectedDocuments = selectedRows.map((row) => row.original);
  const isRestoreMode = Boolean(onBulkRestoreRequest);
  const cancellableDocuments = selectedDocuments.filter(
    (document) => document.lastRun?.status === "queued" || document.lastRun?.status === "running",
  );
  const reprocessableDocuments = selectedDocuments.filter(
    (document) => document.lastRun?.status !== "queued" && document.lastRun?.status !== "running",
  );
  const selectedCount = table.getFilteredSelectedRowModel().rows.length;
  const showRunActions =
    (cancellableDocuments.length > 0 && Boolean(onBulkCancelRequest)) ||
    (reprocessableDocuments.length > 0 && Boolean(onBulkReprocessRequest));
  const showOrganizeMenu = Boolean(onBulkAssignRequest || onBulkTagRequest);
  const showDownloadMenu = Boolean(onBulkDownloadRequest || onBulkDownloadOriginalRequest);
  const showSecondaryActions =
    showOrganizeMenu || showDownloadMenu || Boolean(onBulkDeleteRequest);
  const actionBar = isRestoreMode ? (
    <ActionBar
      open={selectedCount > 0}
      onOpenChange={(open) => {
        if (!open) {
          table.toggleAllRowsSelected(false);
        }
      }}
    >
      <ActionBarSelection>{selectedCount} selected</ActionBarSelection>
      <ActionBarSeparator />
      <ActionBarGroup>
        <ActionBarItem
          variant="secondary"
          size="sm"
          onSelect={() => onBulkRestoreRequest?.(selectedDocuments)}
        >
          Restore ({selectedDocuments.length})
        </ActionBarItem>
        <ActionBarItem variant="outline" size="sm" onSelect={() => table.toggleAllRowsSelected(false)}>
          Clear selection
        </ActionBarItem>
      </ActionBarGroup>
    </ActionBar>
  ) : (
    <ActionBar
      open={selectedCount > 0}
      onOpenChange={(open) => {
        if (!open) {
          table.toggleAllRowsSelected(false);
        }
      }}
    >
      <ActionBarSelection>{selectedCount} selected</ActionBarSelection>
      <ActionBarSeparator />
      <ActionBarGroup>
        {cancellableDocuments.length > 0 && onBulkCancelRequest ? (
          <ActionBarItem
            variant="secondary"
            size="sm"
            onSelect={() => onBulkCancelRequest(cancellableDocuments)}
          >
            Cancel runs ({cancellableDocuments.length})
          </ActionBarItem>
        ) : null}
        {reprocessableDocuments.length > 0 && onBulkReprocessRequest ? (
          <ActionBarItem
            variant="outline"
            size="sm"
            onSelect={() => onBulkReprocessRequest(reprocessableDocuments)}
          >
            Reprocess ({reprocessableDocuments.length})
          </ActionBarItem>
        ) : null}
      </ActionBarGroup>
      {showRunActions && showSecondaryActions ? <ActionBarSeparator /> : null}
      <ActionBarGroup>
        {showOrganizeMenu ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <ActionBarItem
                variant="outline"
                size="sm"
                onSelect={(event) => event.preventDefault()}
              >
                Organize
              </ActionBarItem>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" side="top">
              {onBulkAssignRequest ? (
                <DropdownMenuItem
                  onSelect={() => onBulkAssignRequest(selectedDocuments)}
                >
                  Assign…
                </DropdownMenuItem>
              ) : null}
              {onBulkTagRequest ? (
                <DropdownMenuItem
                  onSelect={() => onBulkTagRequest(selectedDocuments)}
                >
                  Edit tags…
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        {showDownloadMenu ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <ActionBarItem
                variant="outline"
                size="sm"
                onSelect={(event) => event.preventDefault()}
              >
                Download
              </ActionBarItem>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" side="top">
              {onBulkDownloadRequest ? (
                <DropdownMenuItem
                  onSelect={() => onBulkDownloadRequest(selectedDocuments)}
                >
                  Download ({selectedDocuments.length})
                </DropdownMenuItem>
              ) : null}
              {onBulkDownloadOriginalRequest ? (
                <DropdownMenuItem
                  onSelect={() => onBulkDownloadOriginalRequest(selectedDocuments)}
                >
                  Download original ({selectedDocuments.length})
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        {onBulkDeleteRequest ? (
          <ActionBarItem
            variant="destructive"
            size="sm"
            onSelect={() => onBulkDeleteRequest(selectedDocuments)}
          >
            Delete ({selectedDocuments.length})
          </ActionBarItem>
        ) : null}
        <ActionBarItem variant="outline" size="sm" onSelect={() => table.toggleAllRowsSelected(false)}>
          Clear selection
        </ActionBarItem>
      </ActionBarGroup>
    </ActionBar>
  );

  const toolbarShellClassName =
    "rounded-xl border border-border/60 bg-card/90 px-2 py-2 shadow-sm";

  const toolbar = (
    <div className={toolbarShellClassName}>
      <div className="documents-toolbar-row flex min-w-0 flex-wrap items-center gap-2">
        {leadingToolbarActions ? (
          <div className="min-w-0 shrink-0">{leadingToolbarActions}</div>
        ) : null}
        <DataTableSortList table={table} align="start" />
        <DataTableFilterList
          table={table}
          align="start"
          debounceMs={debounceMs}
          throttleMs={throttleMs}
          shallow={shallow}
        />
        <DataTableViewOptions
          table={table}
          align="end"
          buttonClassName="ml-0 h-8 font-normal"
        />
        {toolbarActions ? (
          <div className="ml-auto min-w-0 flex flex-wrap items-center justify-end gap-2">{toolbarActions}</div>
        ) : null}
      </div>
      <div className="mt-2">
        <DocumentsActiveFiltersRail table={table} />
      </div>
    </div>
  );

  const mobileCards = (
    <div className="space-y-3">
      {table.getRowModel().rows.length > 0 ? (
        table.getRowModel().rows.map((row) => (
          <DocumentsMobileCard
            key={row.id}
            row={row}
            presenceEntries={rowPresence?.get(row.original.id) ?? []}
            actions={buildRowContextMenuItems ? buildRowContextMenuItems(row.original) : []}
            onActivate={onRowActivate}
          />
        ))
      ) : (
        <div className="rounded-lg border bg-card py-10 text-center text-sm text-muted-foreground">No results.</div>
      )}
    </div>
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
      {toolbar}
      {isMobile ? (
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2.5 overflow-auto">
          {mobileCards}
          <DataTablePagination table={table} />
          {actionBar}
        </div>
      ) : (
        <>
          <DataTable
            table={table}
            actionBar={actionBar}
            onRowActivate={
              onRowActivate
                ? (row) => {
                    onRowActivate(row.original);
                  }
                : undefined
            }
            onRowContextMenu={
              buildRowContextMenuItems
                ? (row, position) => {
                    const items = buildRowContextMenuItems(row.original);
                    if (items.length === 0) return;
                    setRowContextMenu({ position, items });
                  }
                : undefined
            }
            className="documents-table min-h-0 min-w-0 flex-1 overflow-hidden"
          />
          <ContextMenu
            open={Boolean(rowContextMenu)}
            position={rowContextMenu?.position ?? null}
            onClose={() => setRowContextMenu(null)}
            items={rowContextMenu?.items ?? []}
            appearance="light"
          />
        </>
      )}
    </div>
  );
}
