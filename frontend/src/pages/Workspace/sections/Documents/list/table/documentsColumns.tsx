import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import type { RunStatus } from "@/types";
import type { FilterVariant } from "@/types/data-table";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { Checkbox } from "@/components/ui/checkbox";
import type { DocumentPresenceEntry } from "@/pages/Workspace/hooks/presence/presenceParticipants";

import type { DocumentRow, FileType, WorkspacePerson } from "../../shared/types";
import { fileTypeLabel, formatBytes, formatTimestamp, shortId } from "../../shared/utils";
import { AssigneeCell } from "./cells/AssigneeCell";
import { DocumentNameCell } from "./cells/DocumentNameCell";
import { DocumentRunPhaseCell } from "./cells/DocumentRunPhaseCell";
import { TagsCell } from "./cells/TagsCell";

export type DocumentsColumnContext = {
  lifecycle: "active" | "archived";
  people: WorkspacePerson[];
  currentUserId: string;
  tagOptions: string[];
  onTagOptionsChange?: (nextOptions: string[]) => void;
  onCreateTag?: (tag: string) => void | Promise<void>;
  rowPresence?: Map<string, DocumentPresenceEntry[]>;
  onOpenPreview?: (documentId: string) => void;
  onOpenActivity?: (documentId: string) => void;
  onAssign: (documentId: string, assigneeId: string | null) => void;
  onToggleTag: (documentId: string, tag: string) => void;
  onRenameRequest: (document: DocumentRow) => void;
  onDeleteRequest: (document: DocumentRow) => void;
  onRestoreRequest: (document: DocumentRow) => void;
  onDownloadLatest: (document: DocumentRow) => void;
  onDownloadOriginal: (document: DocumentRow) => void;
  onDownloadEventsLog: (document: DocumentRow) => void;
  onReprocessRequest: (document: DocumentRow) => void;
  onCancelRunRequest: (document: DocumentRow) => void;
  isRowActionPending?: (documentId: string) => boolean;
};

type DocumentsColumnMeta = {
  label?: string;
  placeholder?: string;
  variant?: FilterVariant;
  options?: Array<{ label: string; value: string }>;
  unit?: string;
  headerClassName?: string;
  cellClassName?: string;
};

export function useDocumentsColumns({
  lifecycle,
  people,
  currentUserId,
  tagOptions,
  onTagOptionsChange,
  onCreateTag,
  rowPresence,
  onOpenPreview,
  onOpenActivity,
  onAssign,
  onToggleTag,
  onRenameRequest,
  onDeleteRequest,
  onRestoreRequest,
  onDownloadLatest,
  onDownloadOriginal,
  onDownloadEventsLog,
  onReprocessRequest,
  onCancelRunRequest,
  isRowActionPending,
}: DocumentsColumnContext) {
  const runStatusOptions = useMemo(() => {
    const statuses = (["queued", "running", "succeeded", "failed", "cancelled"] as RunStatus[]).map((value) => ({
      value,
      label: value[0]?.toUpperCase() + value.slice(1),
    }));
    return [{ value: "__empty__", label: "No runs" }, ...statuses];
  }, []);

  const fileTypeOptions = useMemo(
    () =>
      (["xlsx", "xls", "csv", "pdf"] as FileType[]).map((value) => ({
        value,
        label: fileTypeLabel(value),
      })),
    [],
  );

  const memberOptions = useMemo(
    () => people.map((person) => ({ label: person.label, value: person.id })),
    [people],
  );
  const assigneeFilterOptions = useMemo(() => {
    const options = [{ label: "Me", value: "me" }, ...memberOptions];
    return Array.from(new Map(options.map((option) => [option.value, option])).values());
  }, [memberOptions]);

  const tagFilterOptions = useMemo(
    () => tagOptions.map((tag) => ({ label: tag, value: tag })),
    [tagOptions],
  );

  return useMemo<ColumnDef<DocumentRow>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <div className="flex items-center justify-center" data-ignore-row-click>
            <Checkbox
              checked={
                table.getIsAllPageRowsSelected() ||
                (table.getIsSomePageRowsSelected() && "indeterminate")
              }
              onCheckedChange={(value) => table.toggleAllPageRowsSelected(Boolean(value))}
              aria-label="Select all rows"
            />
          </div>
        ),
        cell: ({ row }) => (
          <div className="flex items-center justify-center" data-ignore-row-click>
            <Checkbox
              checked={row.getIsSelected()}
              onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
              aria-label="Select row"
            />
          </div>
        ),
        enableSorting: false,
        enableHiding: false,
        enableColumnFilter: false,
        enableResizing: false,
        meta: {
          headerClassName: "px-0",
          cellClassName: "px-0",
        } as DocumentsColumnMeta,
        size: 36,
        minSize: 36,
        maxSize: 36,
      },
      {
        id: "name",
        accessorKey: "name",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Document" />,
        cell: ({ row }) => {
          const rowPending = isRowActionPending?.(row.original.id) ?? false;
          return (
            <DocumentNameCell
              document={row.original}
              lifecycle={lifecycle}
              presenceEntries={rowPresence?.get(row.original.id) ?? []}
              isBusy={rowPending}
              currentUserId={currentUserId}
              onOpenPreview={onOpenPreview ? () => onOpenPreview(row.original.id) : undefined}
              onOpenActivity={onOpenActivity ? () => onOpenActivity(row.original.id) : undefined}
              onRenameRequest={() => onRenameRequest(row.original)}
              onAssignToMe={() => onAssign(row.original.id, currentUserId)}
              onDeleteRequest={onDeleteRequest}
              onRestoreRequest={onRestoreRequest}
              onDownloadLatest={onDownloadLatest}
              onDownloadOriginal={onDownloadOriginal}
              onDownloadEventsLog={onDownloadEventsLog}
              onReprocessRequest={onReprocessRequest}
              onCancelRunRequest={onCancelRunRequest}
            />
          );
        },
        meta: {
          label: "Document",
          placeholder: "Search documents...",
          variant: "text",
          cellClassName: "overflow-hidden",
        } as DocumentsColumnMeta,
        size: 360,
        enableColumnFilter: true,
        enableHiding: false,
        minSize: 280,
        maxSize: 460,
      },
      {
        id: "assigneeId",
        accessorFn: (row) => row.assignee?.id ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Assignee" />,
        cell: ({ row }) => (
          <AssigneeCell
            assigneeId={row.original.assignee?.id ?? null}
            people={people}
            currentUserId={currentUserId}
            onAssign={(assigneeId) => onAssign(row.original.id, assigneeId)}
            disabled={isRowActionPending?.(row.original.id) ?? false}
          />
        ),
        meta: {
          label: "Assignee",
          variant: "multiSelect",
          options: assigneeFilterOptions,
        } as DocumentsColumnMeta,
        size: 196,
        minSize: 196,
        maxSize: 220,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: false,
      },
      {
        id: "mentionedUserId",
        header: () => null,
        cell: () => null,
        meta: {
          label: "Mentioned",
          variant: "multiSelect",
          options: assigneeFilterOptions,
        } as DocumentsColumnMeta,
        size: 1,
        minSize: 1,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: false,
        enableResizing: false,
      },
      {
        id: "tags",
        accessorKey: "tags",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Tags" />,
        cell: ({ row }) => (
          <TagsCell
            selected={row.original.tags ?? []}
            tagOptions={tagOptions}
            onToggle={(tag) => onToggleTag(row.original.id, tag)}
            onTagOptionsChange={onTagOptionsChange}
            onCreateTag={onCreateTag}
            disabled={isRowActionPending?.(row.original.id) ?? false}
          />
        ),
        meta: {
          label: "Tags",
          variant: "multiSelect",
          options: tagFilterOptions,
        } as DocumentsColumnMeta,
        size: 196,
        minSize: 196,
        maxSize: 260,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "lastRunPhase",
        accessorFn: (row) => row.lastRun?.status ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Run status" />,
        cell: ({ row }) => (
          <DocumentRunPhaseCell
            status={row.original.lastRun?.status ?? null}
            uploadProgress={row.original.uploadProgress ?? null}
          />
        ),
        meta: {
          label: "Run status",
          variant: "multiSelect",
          options: runStatusOptions,
        } as DocumentsColumnMeta,
        size: 156,
        minSize: 156,
        maxSize: 160,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "lastRunAt",
        accessorFn: (row) =>
          row.lastRun?.completedAt ?? row.lastRun?.startedAt ?? row.lastRun?.createdAt ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Last Run" />,
        cell: ({ row }) => {
          const value = row.getValue<string | null>("lastRunAt");
          return <TimestampCell value={value} />;
        },
        meta: {
          label: "Last Run",
          cellClassName: "align-middle",
        } as DocumentsColumnMeta,
        size: 124,
        minSize: 112,
        maxSize: 150,
        enableHiding: true,
      },
      {
        id: "updatedAt",
        accessorKey: "updatedAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Updated" />,
        cell: ({ row }) => <TimestampCell value={row.getValue<string>("updatedAt")} />,
        meta: {
          label: "Updated",
          variant: "dateRange",
          cellClassName: "align-middle",
        } as DocumentsColumnMeta,
        size: 124,
        minSize: 112,
        maxSize: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "createdAt",
        accessorKey: "createdAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Created" />,
        cell: ({ row }) => <TimestampCell value={row.getValue<string>("createdAt")} />,
        meta: {
          label: "Created",
          variant: "dateRange",
          cellClassName: "align-middle",
        } as DocumentsColumnMeta,
        size: 124,
        minSize: 112,
        maxSize: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "deletedAt",
        accessorKey: "deletedAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Archived" />,
        cell: ({ row }) => {
          const value = row.getValue<string | null>("deletedAt");
          return <TimestampCell value={value} />;
        },
        meta: {
          label: "Archived",
          cellClassName: "align-middle",
        } as DocumentsColumnMeta,
        size: 124,
        minSize: 112,
        maxSize: 150,
        enableColumnFilter: false,
        enableHiding: true,
      },
      {
        id: "fileType",
        accessorKey: "fileType",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Type" />,
        cell: ({ row }) => fileTypeLabel(row.getValue<FileType>("fileType")),
        meta: {
          label: "Type",
          variant: "multiSelect",
          options: fileTypeOptions,
        } as DocumentsColumnMeta,
        size: 72,
        minSize: 64,
        maxSize: 96,
        enableColumnFilter: true,
        enableSorting: false,
      },
      {
        id: "uploaderId",
        accessorFn: (row) => row.uploader?.id ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Uploader" />,
        cell: ({ row }) => renderUserSummary(row.original.uploader),
        meta: {
          label: "Uploader",
          variant: "multiSelect",
          options: memberOptions,
        } as DocumentsColumnMeta,
        size: 156,
        minSize: 128,
        maxSize: 220,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "byteSize",
        accessorKey: "byteSize",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Size" />,
        cell: ({ row }) => formatBytes(row.getValue<number>("byteSize")),
        meta: {
          label: "Size",
          variant: "number",
          unit: "bytes",
        } as DocumentsColumnMeta,
        size: 88,
        minSize: 72,
        maxSize: 120,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "activityAt",
        accessorKey: "activityAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Activity" />,
        cell: ({ row }) => <TimestampCell value={row.getValue<string>("activityAt")} />,
        meta: {
          label: "Activity",
          variant: "dateRange",
          cellClassName: "align-middle",
        } as DocumentsColumnMeta,
        size: 124,
        minSize: 112,
        maxSize: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "id",
        accessorKey: "id",
        header: ({ column }) => <DataTableColumnHeader column={column} label="ID" />,
        cell: ({ row }) => (
          <span className="font-mono text-xs text-muted-foreground" title={row.getValue<string>("id")}>
            {shortId(row.getValue<string>("id"))}
          </span>
        ),
        meta: {
          label: "ID",
        } as DocumentsColumnMeta,
        size: 96,
        minSize: 80,
        maxSize: 128,
        enableHiding: true,
      },
    ],
    [
      lifecycle,
      fileTypeOptions,
      isRowActionPending,
      assigneeFilterOptions,
      currentUserId,
      memberOptions,
      onCreateTag,
      onOpenActivity,
      onOpenPreview,
      onAssign,
      onDeleteRequest,
      onRestoreRequest,
      onDownloadLatest,
      onDownloadOriginal,
      onDownloadEventsLog,
      onReprocessRequest,
      onCancelRunRequest,
      onRenameRequest,
      onTagOptionsChange,
      onToggleTag,
      people,
      rowPresence,
      runStatusOptions,
      tagFilterOptions,
      tagOptions,
    ],
  );
}

function renderUserSummary(user: DocumentRow["uploader"]) {
  if (!user) {
    return <span className="text-muted-foreground">-</span>;
  }

  const primary = user.name ?? user.email ?? "Unknown";
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="truncate">{primary}</span>
      {user.email && user.email !== primary ? (
        <span className="truncate text-xs text-muted-foreground">{user.email}</span>
      ) : null}
    </div>
  );
}

function TimestampCell({ value }: { value: string | null | undefined }) {
  if (!value) {
    return <span className="text-muted-foreground">-</span>;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return <span className="truncate text-sm" title={value}>{value}</span>;
  }

  return (
    <time dateTime={value} title={formatTimestamp(value)} className="flex min-w-0 flex-col leading-tight">
      <span className="truncate">{date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</span>
      <span className="truncate text-xs text-muted-foreground">
        {date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
      </span>
    </time>
  );
}
