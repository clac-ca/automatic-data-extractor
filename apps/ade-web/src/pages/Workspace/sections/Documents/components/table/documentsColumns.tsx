import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import type { PresenceParticipant } from "@/types/presence";

import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";

import type { DocumentRow, DocumentRunPhase, FileType, MappingHealth, WorkspacePerson } from "../../types";
import { fileTypeLabel, formatBytes, formatTimestamp, shortId } from "../../utils";
import { ActionsCell } from "./cells/ActionsCell";
import { AssigneeCell } from "./cells/AssigneeCell";
import { DocumentNameCell } from "./cells/DocumentNameCell";
import { DocumentRunPhaseCell } from "./cells/DocumentRunPhaseCell";
import { TagsCell } from "./cells/TagsCell";

export type DocumentsColumnContext = {
  filterMode: "simple" | "advanced";
  people: WorkspacePerson[];
  tagOptions: string[];
  rowPresence?: Map<string, PresenceParticipant[]>;
  selectedDocumentId?: string | null;
  isPreviewOpen: boolean;
  isCommentsOpen: boolean;
  onOpenPreview?: (documentId: string) => void;
  onTogglePreview: (documentId: string) => void;
  onToggleComments: (documentId: string) => void;
  onAssign: (documentId: string, assigneeId: string | null) => void;
  onToggleTag: (documentId: string, tag: string) => void;
  onDeleteRequest: (document: DocumentRow) => void;
  onDownloadOutput: (document: DocumentRow) => void;
  onDownloadOriginal: (document: DocumentRow) => void;
  isRowActionPending?: (documentId: string) => boolean;
};

export function useDocumentsColumns({
  filterMode,
  people,
  tagOptions,
  rowPresence,
  selectedDocumentId,
  isPreviewOpen,
  isCommentsOpen,
  onOpenPreview,
  onTogglePreview,
  onToggleComments,
  onAssign,
  onToggleTag,
  onDeleteRequest,
  onDownloadOutput,
  onDownloadOriginal,
  isRowActionPending,
}: DocumentsColumnContext) {
  const enableAdvancedOnly = filterMode === "advanced";
  const runPhaseOptions = useMemo(() => {
    const phases = (["queued", "building", "running", "succeeded", "failed"] as DocumentRunPhase[]).map(
      (value) => ({
        value,
        label: value[0]?.toUpperCase() + value.slice(1),
      }),
    );
    return [{ value: "__empty__", label: "No runs" }, ...phases];
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

  const tagFilterOptions = useMemo(
    () => tagOptions.map((tag) => ({ label: tag, value: tag })),
    [tagOptions],
  );

  return useMemo<ColumnDef<DocumentRow>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <div className="flex items-center justify-center">
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
          <div className="flex items-center justify-center">
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
        size: 48,
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
        },
        size: 120,
        enableHiding: true,
      },
      {
        id: "name",
        accessorKey: "name",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Document" />,
        cell: ({ row }) => (
          <DocumentNameCell
            name={row.getValue<string>("name")}
            viewers={rowPresence?.get(row.original.id) ?? []}
            isSelected={row.original.id === selectedDocumentId}
            onOpen={
              onOpenPreview ? () => onOpenPreview(row.original.id) : undefined
            }
          />
        ),
        meta: {
          label: "Document",
          placeholder: "Search documents...",
          variant: "text",
        },
        size: 260,
        enableColumnFilter: enableAdvancedOnly,
        enableHiding: false,
      },
      {
        id: "lastRunPhase",
        accessorFn: (row) => row.lastRun?.phase ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Run phase" />,
        cell: ({ row }) => (
          <DocumentRunPhaseCell
            phase={row.original.lastRun?.phase ?? null}
            uploadProgress={row.original.uploadProgress ?? null}
          />
        ),
        meta: {
          label: "Run phase",
          variant: "multiSelect",
          options: runPhaseOptions,
        },
        size: 130,
        enableColumnFilter: true,
        enableHiding: false,
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
        },
        size: 100,
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
        },
        size: 160,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "assigneeId",
        accessorFn: (row) => row.assignee?.id ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Assignee" />,
        cell: ({ row }) => (
          <AssigneeCell
            assigneeId={row.original.assignee?.id ?? null}
            people={people}
            onAssign={(assigneeId) => onAssign(row.original.id, assigneeId)}
            disabled={isRowActionPending?.(row.original.id) ?? false}
          />
        ),
        meta: {
          label: "Assignee",
          variant: "multiSelect",
          options: memberOptions,
        },
        size: 160,
        enableColumnFilter: true,
        enableSorting: false,
        enableHiding: false,
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
            disabled={isRowActionPending?.(row.original.id) ?? false}
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
        header: ({ column }) => <DataTableColumnHeader column={column} label="Size" />,
        cell: ({ row }) => formatBytes(row.getValue<number>("byteSize")),
        meta: {
          label: "Size",
          variant: "number",
          unit: "bytes",
        },
        size: 110,
        enableColumnFilter: enableAdvancedOnly,
        enableHiding: true,
      },
      {
        id: "latestResult",
        accessorKey: "latestResult",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Result" />,
        cell: ({ row }) => renderLatestResult(row.original.latestResult),
        meta: {
          label: "Result",
        },
        size: 200,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "hasOutput",
        accessorFn: (row) => (row.lastSuccessfulRun ? "true" : "false"),
        header: ({ column }) => <DataTableColumnHeader column={column} label="Has Output" />,
        cell: ({ row }) => (row.original.lastSuccessfulRun ? "Yes" : "No"),
        meta: {
          label: "Has Output",
          variant: "boolean",
        },
        size: 110,
        enableColumnFilter: enableAdvancedOnly,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "createdAt",
        accessorKey: "createdAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Created" />,
        cell: ({ row }) => formatTimestamp(row.getValue<string>("createdAt")),
        meta: {
          label: "Created",
          variant: "dateRange",
        },
        size: 150,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "updatedAt",
        accessorKey: "updatedAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Updated" />,
        cell: ({ row }) => formatTimestamp(row.getValue<string>("updatedAt")),
        meta: {
          label: "Updated",
          variant: "dateRange",
        },
        size: 150,
        enableColumnFilter: enableAdvancedOnly,
        enableHiding: true,
      },
      {
        id: "activityAt",
        accessorKey: "activityAt",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Activity" />,
        cell: ({ row }) => formatTimestamp(row.getValue<string>("activityAt")),
        meta: {
          label: "Activity",
          variant: "dateRange",
        },
        size: 150,
        enableColumnFilter: enableAdvancedOnly,
        enableHiding: true,
      },
      {
        id: "lastRunAt",
        accessorFn: (row) =>
          row.lastRun?.completedAt ?? row.lastRun?.startedAt ?? row.lastRun?.createdAt ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Last Run" />,
        cell: ({ row }) => renderRunSummary(row.original.lastRun),
        meta: {
          label: "Last Run",
        },
        size: 180,
        enableHiding: true,
      },
      {
        id: "lastSuccessfulRun",
        accessorFn: (row) =>
          row.lastSuccessfulRun?.completedAt ?? row.lastSuccessfulRun?.startedAt ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Last Success" />,
        cell: ({ row }) => renderRunSummary(row.original.lastSuccessfulRun),
        meta: {
          label: "Last Success",
        },
        size: 180,
        enableSorting: false,
        enableHiding: true,
      },
      {
        id: "actions",
        cell: ({ row }) => (
          <ActionsCell
            document={row.original}
            isPreviewOpen={row.original.id === selectedDocumentId && isPreviewOpen}
            isCommentsOpen={row.original.id === selectedDocumentId && isCommentsOpen}
            onTogglePreview={() => onTogglePreview(row.original.id)}
            onToggleComments={() => onToggleComments(row.original.id)}
            isBusy={isRowActionPending?.(row.original.id) ?? false}
            onDeleteRequest={onDeleteRequest}
            onDownloadOutput={onDownloadOutput}
            onDownloadOriginal={onDownloadOriginal}
          />
        ),
        size: 140,
        enableSorting: false,
        enableHiding: false,
      },
    ],
    [
      enableAdvancedOnly,
      fileTypeOptions,
      isCommentsOpen,
      isPreviewOpen,
      isRowActionPending,
      memberOptions,
      onOpenPreview,
      onAssign,
      onDeleteRequest,
      onDownloadOriginal,
      onDownloadOutput,
      onToggleComments,
      onTogglePreview,
      onToggleTag,
      people,
      rowPresence,
      runPhaseOptions,
      selectedDocumentId,
      tagFilterOptions,
      tagOptions,
    ],
  );
}

function renderLatestResult(result: MappingHealth | null | undefined) {
  if (!result) {
    return <span className="text-muted-foreground">-</span>;
  }
  const pendingOnly = Boolean(result.pending) && result.attention === 0 && result.unmapped === 0;
  if (!pendingOnly && result.attention === 0 && result.unmapped === 0) {
    return <span className="text-muted-foreground">OK</span>;
  }
  return <MappingBadge mapping={result} showPending />;
}

function MappingBadge({ mapping, showPending = false }: { mapping: MappingHealth | null | undefined; showPending?: boolean }) {
  if (!mapping) {
    return null;
  }
  const isPendingOnly = Boolean(mapping.pending && mapping.attention === 0 && mapping.unmapped === 0);

  if (isPendingOnly && !showPending) {
    return null;
  }

  if (isPendingOnly) {
    return (
      <Badge variant="outline" className="gap-1 text-[11px] text-muted-foreground">
        Mapping pending
      </Badge>
    );
  }

  if (mapping.attention === 0 && mapping.unmapped === 0) {
    return null;
  }

  return (
    <Badge variant="outline" className="gap-1 border-border/60 bg-accent text-[11px] text-accent-foreground">
      {mapping.attention > 0 ? `${mapping.attention} need attention` : `${mapping.unmapped} unmapped`}
    </Badge>
  );
}

function formatRunPhase(value: string) {
  if (!value) return "-";
  const normalized = value.replace(/_/g, " ");
  return normalized[0]?.toUpperCase() + normalized.slice(1);
}

function renderRunSummary(run: DocumentRow["lastRun"] | null | undefined) {
  if (!run) {
    return <span className="text-muted-foreground">-</span>;
  }

  const timestamp = run.completedAt ?? run.startedAt ?? run.createdAt;
  const statusLabel = formatRunPhase(String(run.phase ?? run.status));
  return (
    <div className="flex min-w-0 flex-col gap-0.5" title={run.errorSummary ?? undefined}>
      <span className="truncate capitalize">{statusLabel}</span>
      <span className="truncate text-xs text-muted-foreground">
        {timestamp ? formatTimestamp(timestamp) : "-"}
      </span>
    </div>
  );
}

function renderUserSummary(user: DocumentRow["uploader"]) {
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
