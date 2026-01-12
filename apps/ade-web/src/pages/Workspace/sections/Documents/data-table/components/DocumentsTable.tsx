import { useCallback, useEffect, useMemo, useState, type MouseEvent, type ReactNode, type RefObject } from "react";
import type { ColumnDef, Row } from "@tanstack/react-table";
import { Ellipsis } from "lucide-react";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { useDataTable } from "@/hooks/use-data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ContextMenu, type ContextMenuItem } from "@/components/ui/context-menu";
import { cn } from "@/lib/utils";
import { uiStorageKeys } from "@/lib/uiStorageKeys";
import type { PresenceParticipant } from "@schema/presence";
import type { DocumentStatus, FileType, WorkspacePerson } from "@pages/Workspace/sections/Documents/types";
import { DocumentPresenceBadges } from "@pages/Workspace/sections/Documents/components/DocumentPresenceBadges";
import { MappingBadge } from "@pages/Workspace/sections/Documents/components/MappingBadge";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "@pages/Workspace/sections/Documents/components/PeoplePicker";
import { TagPicker } from "@pages/Workspace/sections/Documents/components/TagPicker";
import { UNASSIGNED_KEY } from "@pages/Workspace/sections/Documents/filters";
import { fileTypeLabel, formatBytes, shortId } from "@pages/Workspace/sections/Documents/utils";
import { DocumentPreviewGrid } from "./DocumentPreviewGrid";
import type { DocumentRow } from "../types";
import { DEFAULT_PAGE_SIZE, formatTimestamp } from "../utils";

interface DocumentsTableProps {
  data: DocumentRow[];
  pageCount: number;
  workspaceId: string;
  people: WorkspacePerson[];
  tagOptions: string[];
  rowPresence?: Map<string, PresenceParticipant[]>;
  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onToggleTag: (documentId: string, tag: string) => void;
  onArchive: (documentId: string) => void;
  onRestore: (documentId: string) => void;
  onDeleteRequest: (document: DocumentRow) => void;
  onDownloadOutput: (document: DocumentRow) => void;
  onDownloadOriginal: (document: DocumentRow) => void;
  expandedRowId: string | null;
  onTogglePreview: (documentId: string) => void;
  isRowActionPending?: (documentId: string) => boolean;
  archivedFlashIds?: Set<string>;
  toolbarActions?: ReactNode;
  scrollContainerRef?: RefObject<HTMLDivElement | null>;
  scrollFooter?: ReactNode;
  onVisibleRangeChange?: (range: { startIndex: number; endIndex: number; total: number }) => void;
}

const STATUS_BADGE_STYLES: Record<DocumentStatus, string> = {
  uploading: "border-border/60 bg-muted text-muted-foreground",
  uploaded: "border-border/60 bg-secondary text-secondary-foreground",
  processing: "border-border/60 bg-accent text-accent-foreground",
  processed: "border-primary/20 bg-primary/10 text-primary",
  failed: "border-destructive/40 bg-destructive/10 text-destructive dark:bg-destructive/20",
  archived: "border-border/60 bg-secondary text-secondary-foreground",
};

export function DocumentsTable({
  data,
  pageCount,
  workspaceId,
  people,
  tagOptions,
  rowPresence,
  onAssign,
  onToggleTag,
  onArchive,
  onRestore,
  onDeleteRequest,
  onDownloadOutput,
  onDownloadOriginal,
  expandedRowId,
  onTogglePreview,
  isRowActionPending,
  archivedFlashIds,
  toolbarActions,
  scrollContainerRef,
  scrollFooter,
  onVisibleRangeChange,
}: DocumentsTableProps) {
  const [contextMenu, setContextMenu] = useState<{
    rowId: string;
    position: { x: number; y: number };
  } | null>(null);

  const statusOptions = useMemo(
    () =>
      (["uploading", "uploaded", "processing", "processed", "failed", "archived"] as DocumentStatus[])
        .map((value) => ({
          value,
          label: value[0]?.toUpperCase() + value.slice(1),
        })),
    [],
  );

  const fileTypeOptions = useMemo(
    () =>
      (["xlsx", "xls", "csv", "pdf"] as FileType[]).map((value) => ({
        value,
        label: fileTypeLabel(value),
      })),
    [],
  );

  const memberOptions = useMemo(
    () =>
      people
        .map((person) => ({
          label: person.label,
          value: person.userId ?? person.key.replace(/^user:/, ""),
        }))
        .filter((option) => Boolean(option.value)),
    [people],
  );

  const assigneeOptions = useMemo(
    () => [{ label: "Unassigned", value: UNASSIGNED_KEY }, ...memberOptions],
    [memberOptions],
  );

  const tagFilterOptions = useMemo(
    () => tagOptions.map((tag) => ({ label: tag, value: tag })),
    [tagOptions],
  );

  const runStatusOptions = useMemo(
    () =>
      (["queued", "running", "succeeded", "failed", "cancelled"] as const).map(
        (value) => ({
          value,
          label: value[0]?.toUpperCase() + value.slice(1),
        }),
      ),
    [],
  );

  const sourceOptions = useMemo(
    () => [{ value: "manual_upload", label: "Manual upload" }],
    [],
  );

  const togglePreview = useCallback(
    (rowId: string) => {
      onTogglePreview(rowId);
    },
    [onTogglePreview],
  );

  const contextRow = useMemo(
    () => (contextMenu ? data.find((row) => row.id === contextMenu.rowId) ?? null : null),
    [contextMenu, data],
  );
  const activeMenuRowId = contextMenu?.rowId ?? null;

  useEffect(() => {
    if (contextMenu && !contextRow) {
      setContextMenu(null);
    }
  }, [contextMenu, contextRow]);

  const openContextMenu = useCallback((rowId: string, event: MouseEvent<HTMLElement>) => {
    if (event.type === "contextmenu") {
      event.preventDefault();
    }
    event.stopPropagation();
    setContextMenu({ rowId, position: { x: event.clientX, y: event.clientY } });
  }, []);

  const onRowContextMenu = useCallback(
    (row: Row<DocumentRow>, event: MouseEvent<HTMLTableRowElement>) => {
      const target = event.target as HTMLElement | null;
      if (
        target?.closest("input, textarea, select, [contenteditable='true']")
      ) {
        return;
      }
      openContextMenu(row.original.id, event);
    },
    [openContextMenu],
  );

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextRow) return [];
    const isArchived = contextRow.status === "archived";
    const isPreviewable = Boolean(contextRow.latestSuccessfulRun?.id);
    const isExpanded = contextRow.id === expandedRowId;
    const isBusy = isRowActionPending?.(contextRow.id) ?? false;
    const canDownloadOutput = Boolean(contextRow.latestSuccessfulRun?.id);

    return [
      {
        id: "preview",
        label: isExpanded ? "Hide preview" : "Show preview",
        onSelect: () => togglePreview(contextRow.id),
        disabled: !isPreviewable,
      },
      {
        id: "download-normalized",
        label: "Download normalized",
        onSelect: () => onDownloadOutput(contextRow),
        disabled: !canDownloadOutput,
      },
      {
        id: "download-original",
        label: "Download original",
        onSelect: () => onDownloadOriginal(contextRow),
      },
      {
        id: isArchived ? "restore" : "archive",
        label: isArchived ? "Restore" : "Archive",
        onSelect: () => (isArchived ? onRestore(contextRow.id) : onArchive(contextRow.id)),
        disabled: isBusy,
        dividerAbove: true,
      },
      {
        id: "delete",
        label: "Delete",
        onSelect: () => onDeleteRequest(contextRow),
        disabled: isBusy,
        danger: true,
        dividerAbove: true,
      },
    ];
  }, [
    contextRow,
    expandedRowId,
    isRowActionPending,
    onArchive,
    onDeleteRequest,
    onDownloadOriginal,
    onDownloadOutput,
    onRestore,
    togglePreview,
  ]);

  const columns = useMemo<ColumnDef<DocumentRow>[]>(
    () => [
      {
        id: "id",
        accessorKey: "id",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="ID" />
        ),
        cell: ({ row }) => (
          <span
            className="font-mono text-xs text-muted-foreground"
            title={row.getValue<string>("id")}
          >
            {shortId(row.getValue<string>("id"))}
          </span>
        ),
        meta: {
          label: "ID",
        },
        size: 120,
        enableHiding: true,
      },
      {
        id: "workspaceId",
        accessorKey: "workspaceId",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Workspace" />
        ),
        cell: ({ row }) => (
          <span
            className="font-mono text-xs text-muted-foreground"
            title={row.getValue<string>("workspaceId")}
          >
            {shortId(row.getValue<string>("workspaceId"))}
          </span>
        ),
        meta: {
          label: "Workspace",
        },
        size: 120,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "name",
        accessorKey: "name",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Document" />
        ),
        cell: ({ row }) => {
          const viewers = rowPresence?.get(row.original.id) ?? [];
          return (
            <div className="min-w-0 max-w-full">
              <div
                className="truncate font-medium"
                title={row.getValue<string>("name")}
              >
                {row.getValue<string>("name")}
              </div>
              <DocumentPresenceBadges participants={viewers} />
            </div>
          );
        },
        meta: {
          label: "Document",
          placeholder: "Search documents...",
          variant: "text",
        },
        size: 260,
        enableColumnFilter: false,
        enableHiding: false,
      },
      {
        id: "status",
        accessorKey: "status",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Status" />
        ),
        cell: ({ row }) => {
          const status = row.getValue<string>("status");
          const flash = status === "archived" && (archivedFlashIds?.has(row.original.id) ?? false);
          const uploadProgress = row.original.uploadProgress ?? null;
          const statusTone =
            STATUS_BADGE_STYLES[status as DocumentStatus] ?? "border-border bg-muted text-muted-foreground";
          return (
            <div className="flex min-w-[120px] flex-col gap-1">
              <Badge
                variant="outline"
                className={cn(
                  "capitalize",
                  statusTone,
                  flash && "ring-1 ring-accent/70 animate-pulse",
                )}
              >
                {status}
              </Badge>
              {status === "uploading" && typeof uploadProgress === "number" ? (
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                  <div className="h-1.5 w-16 rounded-full bg-muted">
                    <div
                      className="h-1.5 rounded-full bg-primary"
                      style={{ width: `${Math.max(0, Math.min(100, uploadProgress))}%` }}
                    />
                  </div>
                  <span className="tabular-nums">{Math.round(uploadProgress)}%</span>
                </div>
              ) : null}
            </div>
          );
        },
        meta: {
          label: "Status",
          variant: "multiSelect",
          options: statusOptions,
        },
        size: 120,
        enableColumnFilter: true,
        enableHiding: false,
      },
      {
        id: "fileType",
        accessorKey: "fileType",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Type" />
        ),
        cell: ({ row }) =>
          fileTypeLabel(row.getValue<FileType>("fileType")),
        meta: {
          label: "Type",
          variant: "multiSelect",
          options: fileTypeOptions,
        },
        size: 100,
        enableColumnFilter: true,
        enableSorting: false,
      },
      {
        id: "uploaderId",
        accessorFn: (row) => row.uploader?.id ?? null,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Uploader" />
        ),
        cell: ({ row }) => renderUserSummary(row.original.uploader),
        meta: {
          label: "Uploader",
          variant: "multiSelect",
          options: memberOptions,
        },
        size: 160,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "assigneeId",
        accessorFn: (row) => row.assignee?.id ?? null,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Assignee" />
        ),
        cell: ({ row }) => (
          <PeoplePicker
            people={people}
            value={[row.original.assignee?.id ? `user:${row.original.assignee.id}` : unassignedKey()]}
            onChange={(keys) => onAssign(row.original.id, normalizeSingleAssignee(keys))}
            placeholder="Assignee..."
            includeUnassigned
            disabled={isRowActionPending?.(row.original.id) ?? false}
            buttonClassName="min-w-[140px] bg-background px-2 py-1 text-[11px] shadow-none"
          />
        ),
        meta: {
          label: "Assignee",
          variant: "multiSelect",
          options: assigneeOptions,
        },
        size: 160,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: false,
      },
      {
        id: "tags",
        accessorKey: "tags",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Tags" />
        ),
        cell: ({ row }) => (
          <TagPicker
            workspaceId={workspaceId}
            selected={row.original.tags ?? []}
            onToggle={(tag) => onToggleTag(row.original.id, tag)}
            placeholder="Add tags"
            disabled={isRowActionPending?.(row.original.id) ?? false}
            buttonClassName="min-w-0 max-w-[12rem] bg-background px-2 py-1 text-[11px] shadow-none"
          />
        ),
        meta: {
          label: "Tags",
          variant: "multiSelect",
          options: tagFilterOptions,
        },
        size: 180,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "byteSize",
        accessorKey: "byteSize",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Size" />
        ),
        cell: ({ row }) => formatBytes(row.getValue<number>("byteSize")),
        meta: {
          label: "Size",
          variant: "number",
          unit: "bytes",
        },
        size: 110,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "latestResult",
        accessorKey: "latestResult",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Result" />
        ),
        cell: ({ row }) => renderLatestResult(row.original.latestResult),
        meta: {
          label: "Result",
        },
        size: 140,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "runStatus",
        accessorFn: (row) => row.latestRun?.status ?? null,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Run Status" />
        ),
        cell: ({ row }) => (
          <span className="capitalize">{row.original.latestRun?.status ?? "-"}</span>
        ),
        meta: {
          label: "Run Status",
          variant: "multiSelect",
          options: runStatusOptions,
        },
        size: 120,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "hasOutput",
        accessorFn: (row) => (row.latestSuccessfulRun ? "true" : "false"),
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Has Output" />
        ),
        cell: ({ row }) => (row.original.latestSuccessfulRun ? "Yes" : "No"),
        meta: {
          label: "Has Output",
          variant: "boolean",
        },
        size: 110,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "source",
        accessorFn: () => null,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Source" />
        ),
        cell: () => <span className="text-muted-foreground">-</span>,
        meta: {
          label: "Source",
          variant: "multiSelect",
          options: sourceOptions,
        },
        size: 120,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "createdAt",
        accessorKey: "createdAt",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Created" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("createdAt")),
        meta: {
          label: "Created",
          variant: "date",
        },
        size: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "updatedAt",
        accessorKey: "updatedAt",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Updated" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("updatedAt")),
        meta: {
          label: "Updated",
          variant: "date",
        },
        size: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "activityAt",
        accessorKey: "activityAt",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Activity" />
        ),
        cell: ({ row }) => formatTimestamp(row.getValue<string>("activityAt")),
        meta: {
          label: "Activity",
          variant: "date",
        },
        size: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "latestRunAt",
        accessorFn: (row) => row.latestRun?.completedAt ?? row.latestRun?.startedAt ?? null,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Latest Run" />
        ),
        cell: ({ row }) => renderRunSummary(row.original.latestRun),
        meta: {
          label: "Latest Run",
        },
        size: 180,
        enableHiding: true,
      },
      {
        id: "latestSuccessfulRun",
        accessorFn: (row) =>
          row.latestSuccessfulRun?.completedAt ?? row.latestSuccessfulRun?.startedAt ?? null,
        header: ({ column }) => (
          <DataTableColumnHeader column={column} label="Latest Success" />
        ),
        cell: ({ row }) => renderRunSummary(row.original.latestSuccessfulRun),
        meta: {
          label: "Latest Success",
        },
        size: 180,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "actions",
        cell: ({ row }) => {
          return (
            <div
              className="flex justify-end"
              data-ignore-row-click
              onContextMenu={(event) => openContextMenu(row.original.id, event)}
            >
              <Button
                aria-label="Open menu"
                variant="ghost"
                type="button"
                className="flex size-8 p-0 data-[state=open]:bg-muted"
                data-state={activeMenuRowId === row.original.id ? "open" : "closed"}
                onClick={(event) => openContextMenu(row.original.id, event)}
                aria-expanded={activeMenuRowId === row.original.id}
                aria-haspopup="menu"
              >
                <Ellipsis className="size-4" aria-hidden="true" />
              </Button>
            </div>
          );
        },
        size: 56,
        enableSorting: false,
        enableHiding: false,
      },
    ],
    [
      archivedFlashIds,
      assigneeOptions,
      activeMenuRowId,
      fileTypeOptions,
      isRowActionPending,
      memberOptions,
      onAssign,
      openContextMenu,
      rowPresence,
      onToggleTag,
      people,
      runStatusOptions,
      sourceOptions,
      statusOptions,
      tagFilterOptions,
      workspaceId,
    ],
  );

  const { table, debounceMs, throttleMs, shallow, history, startTransition } = useDataTable({
    data,
    columns,
    pageCount,
    enableColumnResizing: true,
    columnSizingKey: uiStorageKeys.documentsTableColumnSizing(workspaceId),
    defaultColumn: {
      size: 140,
      minSize: 90,
    },
    initialState: {
      sorting: [{ id: "createdAt", desc: true }],
      pagination: { pageSize: DEFAULT_PAGE_SIZE },
      columnVisibility: {
        id: false,
        workspaceId: false,
        fileType: false,
        uploaderId: false,
        byteSize: false,
        runStatus: false,
        hasOutput: false,
        source: false,
        createdAt: false,
        updatedAt: false,
        latestSuccessfulRun: false,
      },
      columnPinning: { right: ["actions"] },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  useEffect(() => {
    const container = scrollContainerRef?.current;
    if (!container) return;

    const updateWidth = () => {
      container.style.setProperty(
        "--documents-preview-width",
        `${container.clientWidth}px`,
      );
    };

    updateWidth();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => updateWidth());
    observer.observe(container);
    return () => observer.disconnect();
  }, [scrollContainerRef]);

  const isRowExpanded = useCallback(
    (row: Row<DocumentRow>) => row.id === expandedRowId,
    [expandedRowId],
  );

  const onRowClick = useCallback(
    (row: Row<DocumentRow>, event: MouseEvent<HTMLTableRowElement>) => {
      const target = event.target as HTMLElement | null;
      if (
        target?.closest(
          "button, a, input, select, textarea, [role='button'], [role='menuitem'], [data-ignore-row-click='true'], [data-ignore-row-click]",
        )
      ) {
        return;
      }
      togglePreview(row.id);
    },
    [togglePreview],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <DataTableAdvancedToolbar table={table}>
        <DataTableSortList table={table} align="start" />
        <DataTableFilterList
          table={table}
          align="start"
          debounceMs={debounceMs}
          throttleMs={throttleMs}
          shallow={shallow}
          history={history}
          startTransition={startTransition}
        />
        {toolbarActions ? (
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {toolbarActions}
          </div>
        ) : null}
      </DataTableAdvancedToolbar>
      <div
        ref={scrollContainerRef}
        className="flex min-h-0 min-w-0 flex-1 flex-col items-start gap-3 overflow-auto rounded-md border border-border bg-background"
      >
        <DataTable
          table={table}
          showPagination={false}
          className="inline-flex min-w-full w-max overflow-visible [&>div]:border-0 [&>div]:overflow-visible [&>div]:rounded-none [&_[data-slot=table]]:min-w-full [&_[data-slot=table]]:w-max [&_[data-slot=table]]:table-fixed [&_[data-slot=table-container]]:max-w-full [&_[data-slot=table-container]]:overflow-visible [&_[data-slot=table-head]]:!sticky [&_[data-slot=table-head]]:top-0 [&_[data-slot=table-head]]:!z-20 [&_[data-slot=table-head]]:bg-background/95 [&_[data-slot=table-head]]:backdrop-blur-sm [&_[data-slot=table-head]]:shadow-[inset_0_-1px_0_0_var(--border)]"
          onRowClick={onRowClick}
          onRowContextMenu={onRowContextMenu}
          stretchColumnId="name"
          isRowExpanded={isRowExpanded}
          expandedRowCellClassName="bg-muted/20 p-0 align-top whitespace-normal overflow-visible"
          virtualize={{
            enabled: !expandedRowId,
            estimateSize: 52,
            overscan: 8,
            getScrollElement: () => scrollContainerRef?.current ?? null,
            onRangeChange: onVisibleRangeChange,
          }}
          renderExpandedRow={(row) => {
            return (
              <div className="min-w-0 max-w-full">
                <div
                  className="sticky left-0 min-w-0 max-w-full"
                  style={{
                    width: "var(--documents-preview-width, 100%)",
                    maxWidth: "var(--documents-preview-width, 100%)",
                  }}
                >
                  {!row.original.latestSuccessfulRun?.id ? (
                    <div className="p-2 text-muted-foreground text-sm">
                      Preview is available after a successful run completes.
                    </div>
                  ) : (
                    <DocumentPreviewGrid document={row.original} />
                  )}
                </div>
              </div>
            );
          }}
        />
        {scrollFooter}
      </div>
      <ContextMenu
        open={Boolean(contextMenu && contextRow)}
        position={contextMenu && contextRow ? contextMenu.position : null}
        onClose={() => setContextMenu(null)}
        items={contextMenuItems}
        appearance="light"
      />
    </div>
  );
}

function renderLatestResult(result: DocumentRow["latestResult"]) {
  if (!result) {
    return <span className="text-muted-foreground">-</span>;
  }
  const pendingOnly = Boolean(result.pending) && result.attention === 0 && result.unmapped === 0;
  if (!pendingOnly && result.attention === 0 && result.unmapped === 0) {
    return <span className="text-muted-foreground">OK</span>;
  }
  return <MappingBadge mapping={result} showPending />;
}

function formatRunStatus(value: string) {
  if (!value) return "-";
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

function renderRunSummary(run: DocumentListRow["latestRun"] | null | undefined) {
  if (!run) {
    return <span className="text-muted-foreground">-</span>;
  }

  const timestamp = run.completedAt ?? run.startedAt;
  const statusLabel = formatRunStatus(String(run.status));
  return (
    <div className="flex min-w-0 flex-col gap-0.5" title={run.errorSummary ?? undefined}>
      <span className="truncate capitalize">{statusLabel}</span>
      <span className="truncate text-xs text-muted-foreground">
        {timestamp ? formatTimestamp(timestamp) : "-"}
      </span>
    </div>
  );
}

function renderUserSummary(user: DocumentListRow["uploader"]) {
  if (!user) {
    return <span className="text-muted-foreground">-</span>;
  }

  const primary = user.name ?? user.email ?? "Unknown";
  const secondary = user.name ? user.email : null;

  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="truncate">{primary}</span>
      {secondary ? (
        <span className="truncate text-xs text-muted-foreground">{secondary}</span>
      ) : null}
    </div>
  );
}
