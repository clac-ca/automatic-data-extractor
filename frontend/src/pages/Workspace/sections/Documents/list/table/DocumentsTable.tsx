import { useEffect, useState, type ReactNode } from "react";
import { type Table } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
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
import type { DocumentRow } from "../../shared/types";
import { DOCUMENTS_PAGE_SIZE_OPTIONS } from "../../shared/constants";
import { DocumentsActiveFiltersRail } from "./DocumentsActiveFiltersRail";

interface DocumentsTableProps {
  table: Table<DocumentRow>;
  debounceMs: number;
  throttleMs: number;
  shallow: boolean;
  leadingToolbarActions?: ReactNode;
  toolbarActions?: ReactNode;
  onPageSizeChange?: (pageSize: number) => void;
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
  leadingToolbarActions,
  toolbarActions,
  onPageSizeChange,
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
  const [rowContextMenu, setRowContextMenu] = useState<{
    position: { x: number; y: number };
    items: ContextMenuItem[];
  } | null>(null);

  useEffect(() => {
    table.toggleAllRowsSelected(false);
  }, [selectionResetToken, table]);

  const selectedRows = table.getFilteredSelectedRowModel().rows;
  const selectedDocuments = selectedRows.map((row) => row.original);
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
  const showOrganizeActions = Boolean(onBulkAssignRequest || onBulkTagRequest);
  const showDownloadMenu = Boolean(onBulkDownloadRequest || onBulkDownloadOriginalRequest);
  const showSecondaryActions =
    showOrganizeActions || showDownloadMenu || Boolean(onBulkDeleteRequest);
  const actionBar = (
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
        {onBulkRestoreRequest ? (
          <ActionBarItem
            variant="secondary"
            size="sm"
            onSelect={() => onBulkRestoreRequest(selectedDocuments)}
          >
            Restore ({selectedDocuments.length})
          </ActionBarItem>
        ) : null}
        {onBulkAssignRequest ? (
          <ActionBarItem
            variant="outline"
            size="sm"
            onSelect={() => onBulkAssignRequest(selectedDocuments)}
          >
            Assign
          </ActionBarItem>
        ) : null}
        {onBulkTagRequest ? (
          <ActionBarItem
            variant="outline"
            size="sm"
            onSelect={() => onBulkTagRequest(selectedDocuments)}
          >
            Edit Tags
          </ActionBarItem>
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
            Archive ({selectedDocuments.length})
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

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
      {toolbar}
      <>
        <DataTable
          table={table}
          actionBar={actionBar}
          pageSizeOptions={DOCUMENTS_PAGE_SIZE_OPTIONS}
          onPageSizeChange={onPageSizeChange}
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
    </div>
  );
}
