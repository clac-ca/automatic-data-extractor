import { useEffect, type ReactNode } from "react";
import type { Table } from "@tanstack/react-table";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import {
  ActionBar,
  ActionBarGroup,
  ActionBarItem,
  ActionBarSelection,
  ActionBarSeparator,
} from "@/components/ui/action-bar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DocumentRow } from "../../shared/types";

interface DocumentsTableProps {
  table: Table<DocumentRow>;
  debounceMs: number;
  throttleMs: number;
  shallow: boolean;
  filterMode: "simple" | "advanced";
  onToggleFilterMode?: () => void;
  leadingToolbarActions?: ReactNode;
  toolbarActions?: ReactNode;
  onBulkReprocessRequest?: (documents: DocumentRow[]) => void;
  onBulkCancelRequest?: (documents: DocumentRow[]) => void;
  onBulkAssignRequest?: (documents: DocumentRow[]) => void;
  onBulkTagRequest?: (documents: DocumentRow[]) => void;
  onBulkDeleteRequest?: (documents: DocumentRow[]) => void;
  onBulkRestoreRequest?: (documents: DocumentRow[]) => void;
  onBulkDownloadRequest?: (documents: DocumentRow[]) => void;
  onBulkDownloadOriginalRequest?: (documents: DocumentRow[]) => void;
  selectionResetToken?: number;
}

export function DocumentsTable({
  table,
  debounceMs,
  throttleMs,
  shallow,
  filterMode,
  onToggleFilterMode,
  leadingToolbarActions,
  toolbarActions,
  onBulkReprocessRequest,
  onBulkCancelRequest,
  onBulkAssignRequest,
  onBulkTagRequest,
  onBulkDeleteRequest,
  onBulkRestoreRequest,
  onBulkDownloadRequest,
  onBulkDownloadOriginalRequest,
  selectionResetToken = 0,
}: DocumentsTableProps) {
  const isAdvanced = filterMode === "advanced";

  useEffect(() => {
    table.toggleAllRowsSelected(false);
  }, [selectionResetToken, table]);

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
  const filterToggle = onToggleFilterMode ? (
    <Button variant="outline" size="sm" onClick={onToggleFilterMode}>
      {isAdvanced ? "Simple filters" : "Advanced filters"}
    </Button>
  ) : null;

  const toolbarTail = filterToggle || toolbarActions ? (
    <>
      {filterToggle}
      {toolbarActions}
    </>
  ) : null;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
      {isAdvanced ? (
        <DataTableAdvancedToolbar table={table} className={toolbarShellClassName}>
          <div className="flex w-full flex-wrap items-center gap-2">
            {leadingToolbarActions ? (
              <div className="min-w-0 flex shrink-0 flex-wrap items-center gap-2">
                {leadingToolbarActions}
              </div>
            ) : null}
            <div className="min-w-0 flex flex-wrap items-center gap-2">
              <DataTableSortList table={table} align="start" />
              <DataTableFilterList
                table={table}
                align="start"
                debounceMs={debounceMs}
                throttleMs={throttleMs}
                shallow={shallow}
              />
            </div>
            {toolbarTail ? (
              <div className="ml-auto min-w-0 flex flex-wrap items-center justify-end gap-2">
                {toolbarTail}
              </div>
            ) : null}
          </div>
        </DataTableAdvancedToolbar>
      ) : (
        <DataTableToolbar table={table} className={toolbarShellClassName}>
          {leadingToolbarActions ? (
            <div className="min-w-0 flex shrink-0 flex-wrap items-center gap-2">
              {leadingToolbarActions}
            </div>
          ) : null}
          <DataTableSortList table={table} align="start" />
          <div className="ml-auto min-w-0 flex flex-wrap items-center justify-end gap-2">
            {filterToggle}
            {toolbarActions}
          </div>
        </DataTableToolbar>
      )}
      <DataTable
        table={table}
        actionBar={actionBar}
        className="documents-table min-h-0 min-w-0 flex-1 overflow-hidden"
      />
    </div>
  );
}
