import { useCallback, useEffect, useMemo, useState, type MouseEvent, type ReactNode, type RefObject } from "react";
import type { ColumnDef, Row } from "@tanstack/react-table";
import { Ellipsis } from "lucide-react";

import { DataTable } from "@/components/data-table/data-table";
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { useDataTable } from "@/hooks/use-data-table";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useSearchParams } from "@app/navigation/urlState";
import type { PresenceParticipant } from "@schema/presence";
import type { DocumentStatus, FileType, WorkspacePerson } from "@pages/Workspace/sections/Documents/types";
import { DocumentPresenceBadges } from "@pages/Workspace/sections/Documents/components/DocumentPresenceBadges";
import { MappingBadge } from "@pages/Workspace/sections/Documents/components/MappingBadge";
import { PeoplePicker, normalizeSingleAssignee, unassignedKey } from "@pages/Workspace/sections/Documents/components/PeoplePicker";
import { TagPicker } from "@pages/Workspace/sections/Documents/components/TagPicker";
import { UNASSIGNED_KEY } from "@pages/Workspace/sections/Documents/filters";
import { fileTypeLabel, formatBytes, shortId } from "@pages/Workspace/sections/Documents/utils";
import { DocumentPreviewGrid } from "./DocumentPreviewGrid";
import type { DocumentListRow } from "../types";
import { DEFAULT_PAGE_SIZE, formatTimestamp } from "../utils";

interface DocumentsTableProps {
  data: DocumentListRow[];
  pageCount: number;
  workspaceId: string;
  people: WorkspacePerson[];
  tagOptions: string[];
  rowPresence?: Map<string, PresenceParticipant[]>;
  onAssign: (documentId: string, assigneeKey: string | null) => void;
  onToggleTag: (documentId: string, tag: string) => void;
  onArchive: (documentId: string) => void;
  onRestore: (documentId: string) => void;
  onDeleteRequest: (document: DocumentListRow) => void;
  expandedRowId: string | null;
  onTogglePreview: (documentId: string) => void;
  isRowActionPending?: (documentId: string) => boolean;
  archivedFlashIds?: Set<string>;
  toolbarActions?: ReactNode;
  scrollContainerRef?: RefObject<HTMLDivElement | null>;
  scrollFooter?: ReactNode;
}

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
  expandedRowId,
  onTogglePreview,
  isRowActionPending,
  archivedFlashIds,
  toolbarActions,
  scrollContainerRef,
  scrollFooter,
}: DocumentsTableProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchValue, setSearchValue] = useState(() => searchParams.get("q") ?? "");

  useEffect(() => {
    setSearchValue(searchParams.get("q") ?? "");
  }, [searchParams]);

  const statusOptions = useMemo(
    () =>
      (["uploaded", "processing", "processed", "failed", "archived"] as DocumentStatus[])
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

  const columns = useMemo<ColumnDef<DocumentListRow>[]>(
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
          return (
            <Badge
              variant="outline"
              className={cn(
                "capitalize",
                status === "archived" &&
                  "border-warning-200 text-warning-900 dark:border-warning-500/60 dark:text-warning-100",
                flash &&
                  "bg-warning-50 ring-1 ring-warning-300/70 animate-pulse dark:bg-warning-500/15",
              )}
            >
              {status}
            </Badge>
          );
        },
        meta: {
          label: "Status",
          variant: "multiSelect",
          options: statusOptions,
        },
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
            buttonClassName="min-w-[140px] bg-background px-2 py-1 text-[11px] shadow-none"
          />
        ),
        meta: {
          label: "Assignee",
          variant: "multiSelect",
          options: assigneeOptions,
        },
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
            buttonClassName="min-w-0 max-w-[12rem] bg-background px-2 py-1 text-[11px] shadow-none"
          />
        ),
        meta: {
          label: "Tags",
          variant: "multiSelect",
          options: tagFilterOptions,
        },
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
        enableColumnFilter: true,
        enableHiding: false,
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
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "actions",
        cell: ({ row }) => {
          const isArchived = row.original.status === "archived";
          const isPreviewable = Boolean(row.original.latestSuccessfulRun?.id);
          const isExpanded = row.id === expandedRowId;
          const isBusy = isRowActionPending?.(row.original.id) ?? false;

          return (
            <div className="flex justify-end" data-ignore-row-click>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    aria-label="Open menu"
                    variant="ghost"
                    className="flex size-8 p-0 data-[state=open]:bg-muted"
                  >
                    <Ellipsis className="size-4" aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-44">
                  <DropdownMenuItem
                    onSelect={() => togglePreview(row.id)}
                    disabled={!isPreviewable}
                  >
                    {isExpanded ? "Hide preview" : "Show preview"}
                  </DropdownMenuItem>
                  {isArchived ? (
                    <DropdownMenuItem
                      onSelect={() => onRestore(row.original.id)}
                      disabled={isBusy}
                    >
                      Restore
                    </DropdownMenuItem>
                  ) : (
                    <DropdownMenuItem
                      onSelect={() => onArchive(row.original.id)}
                      disabled={isBusy}
                    >
                      Archive
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => onDeleteRequest(row.original)}
                    disabled={isBusy}
                  >
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
        size: 40,
        enableSorting: false,
        enableHiding: false,
      },
    ],
    [
      archivedFlashIds,
      assigneeOptions,
      fileTypeOptions,
      expandedRowId,
      isRowActionPending,
      memberOptions,
      onAssign,
      onArchive,
      onDeleteRequest,
      rowPresence,
      onRestore,
      onToggleTag,
      onTogglePreview,
      people,
      runStatusOptions,
      sourceOptions,
      statusOptions,
      tagFilterOptions,
      togglePreview,
      workspaceId,
    ],
  );

  const { table, debounceMs, throttleMs, shallow, history, startTransition } = useDataTable({
    data,
    columns,
    pageCount,
    initialState: {
      sorting: [{ id: "createdAt", desc: true }],
      pagination: { pageSize: DEFAULT_PAGE_SIZE },
      columnVisibility: {
        runStatus: false,
        hasOutput: false,
        source: false,
      },
      columnPinning: { right: ["actions"] },
    },
    getRowId: (row) => row.id,
    enableAdvancedFilter: true,
    clearOnDefault: true,
  });

  const replaceHistory = history !== "push";
  const setSearchParamsSafe = useCallback(
    (value: string) => {
      const applyUpdate = () =>
        setSearchParams((prev) => {
          const params = new URLSearchParams(prev);
          const trimmed = value.trim();
          if (!trimmed) {
            params.delete("q");
          } else {
            params.set("q", trimmed);
          }
          params.delete("page");
          return params;
        }, { replace: replaceHistory });

      if (startTransition) {
        startTransition(() => applyUpdate());
      } else {
        applyUpdate();
      }
    },
    [replaceHistory, setSearchParams, startTransition],
  );

  const debouncedSetSearch = useDebouncedCallback(setSearchParamsSafe, debounceMs);

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
    (row: Row<DocumentListRow>) => row.id === expandedRowId,
    [expandedRowId],
  );

  const onRowClick = useCallback(
    (row: Row<DocumentListRow>, event: MouseEvent<HTMLTableRowElement>) => {
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
        <Input
          value={searchValue}
          onChange={(event) => {
            const nextValue = event.target.value;
            setSearchValue(nextValue);
            debouncedSetSearch(nextValue);
          }}
          placeholder="Search documents..."
          className="h-8 w-full max-w-[240px]"
        />
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
          className="inline-flex min-w-full w-max overflow-visible [&>div]:border-0 [&>div]:overflow-visible [&>div]:rounded-none [&_[data-slot=table]]:min-w-full [&_[data-slot=table]]:w-max [&_[data-slot=table]]:table-fixed [&_[data-slot=table-container]]:max-w-full [&_[data-slot=table-container]]:overflow-visible [&_[data-slot=table-head]]:!sticky [&_[data-slot=table-head]]:top-0 [&_[data-slot=table-head]]:!z-20 [&_[data-slot=table-head]]:bg-background/95 [&_[data-slot=table-head]]:backdrop-blur-sm [&_[data-slot=table-head]]:shadow-[inset_0_-1px_0_0_rgb(var(--sys-color-border))]"
          onRowClick={onRowClick}
          isRowExpanded={isRowExpanded}
          expandedRowCellClassName="bg-muted/20 p-0 align-top whitespace-normal overflow-visible"
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
    </div>
  );
}

function renderLatestResult(result: DocumentListRow["latestResult"]) {
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
