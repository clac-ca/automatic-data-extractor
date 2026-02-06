import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";

import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";

import { RunActionsCell } from "./cells/RunActionsCell";
import { RunInputCell } from "./cells/RunInputCell";
import { RunStatusCell } from "./cells/RunStatusCell";
import { fileTypeLabel, formatTimestamp } from "../../utils";
import type { RunRecord } from "../../types";

export type RunsColumnContext = {
  activeRunId: string | null;
  onTogglePreview: (runId: string) => void;
};

export function useRunsColumns({ activeRunId, onTogglePreview }: RunsColumnContext) {
  const statusOptions = useMemo(
    () =>
      (["queued", "running", "succeeded", "failed"] as RunRecord["status"][]).map((value) => ({
        value,
        label: value[0]?.toUpperCase() + value.slice(1),
      })),
    [],
  );

  const fileTypeOptions = useMemo(
    () =>
      (["xlsx", "xls", "csv", "pdf"] as const).map((value) => ({
        value,
        label: fileTypeLabel(value),
      })),
    [],
  );

  return useMemo<ColumnDef<RunRecord>[]>(
    () => [
      {
        id: "id",
        accessorKey: "id",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Run ID" />,
        cell: ({ row }) => (
          <span className="font-mono text-xs text-muted-foreground" title={row.getValue<string>("id")}>
            {row.getValue<string>("id")}
          </span>
        ),
        size: 160,
        enableSorting: true,
        enableColumnFilter: false,
        enableHiding: true,
      },
      {
        id: "status",
        accessorKey: "status",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Status" />,
        cell: ({ row }) => <RunStatusCell status={row.getValue<RunRecord["status"]>("status")} />,
        meta: {
          label: "Status",
          variant: "multiSelect",
          options: statusOptions,
        },
        size: 140,
        enableSorting: true,
        enableColumnFilter: true,
        enableHiding: false,
      },
      {
        id: "inputName",
        accessorKey: "inputName",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Input" />,
        cell: ({ row }) => <RunInputCell name={row.getValue<string>("inputName")} id={row.original.id} />,
        size: 260,
        enableSorting: false,
        enableColumnFilter: false,
        enableHiding: false,
      },
      {
        id: "configurationId",
        accessorKey: "configurationId",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Configuration" />,
        cell: ({ row }) => (
          <span className="truncate text-xs text-foreground" title={row.original.configLabel}>
            {row.original.configLabel}
          </span>
        ),
        meta: {
          label: "Configuration",
          variant: "text",
        },
        size: 200,
        enableSorting: false,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "createdAt",
        accessorFn: (row) => row.raw.created_at,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Created" />,
        cell: ({ row }) => formatTimestamp(row.getValue<string | null>("createdAt")),
        meta: {
          label: "Created",
          variant: "dateRange",
        },
        size: 160,
        enableSorting: true,
        enableColumnFilter: true,
        enableHiding: false,
      },
      {
        id: "startedAt",
        accessorFn: (row) => row.raw.started_at ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Started" />,
        cell: ({ row }) => formatTimestamp(row.getValue<string | null>("startedAt")),
        meta: {
          label: "Started",
          variant: "date",
        },
        size: 160,
        enableSorting: true,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "completedAt",
        accessorFn: (row) => row.raw.completed_at ?? null,
        header: ({ column }) => <DataTableColumnHeader column={column} label="Completed" />,
        cell: ({ row }) => formatTimestamp(row.getValue<string | null>("completedAt")),
        meta: {
          label: "Completed",
          variant: "date",
        },
        size: 160,
        enableSorting: true,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "duration",
        accessorKey: "durationLabel",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Duration" />,
        cell: ({ row }) => <span className="text-xs text-muted-foreground">{row.original.durationLabel}</span>,
        size: 120,
        enableSorting: false,
        enableColumnFilter: false,
        enableHiding: false,
      },
      {
        id: "fileType",
        accessorKey: "fileType",
        header: ({ column }) => <DataTableColumnHeader column={column} label="Type" />,
        cell: ({ row }) => fileTypeLabel(row.getValue<RunRecord["fileType"]>("fileType")),
        meta: {
          label: "Type",
          variant: "multiSelect",
          options: fileTypeOptions,
        },
        size: 110,
        enableSorting: false,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "hasOutput",
        accessorFn: (row) => (row.status === "succeeded" ? "true" : "false"),
        header: ({ column }) => <DataTableColumnHeader column={column} label="Has Output" />,
        cell: ({ row }) => (row.original.status === "succeeded" ? "Yes" : "No"),
        meta: {
          label: "Has Output",
          variant: "boolean",
        },
        size: 120,
        enableSorting: false,
        enableColumnFilter: true,
        enableHiding: true,
      },
      {
        id: "actions",
        header: () => <div className="text-right text-xs font-semibold uppercase text-muted-foreground">Actions</div>,
        cell: ({ row }) => (
          <RunActionsCell
            run={row.original}
            isActive={row.original.id === activeRunId}
            onTogglePreview={() => onTogglePreview(row.original.id)}
          />
        ),
        size: 140,
        enableSorting: false,
        enableColumnFilter: false,
        enableHiding: false,
      },
    ],
    [activeRunId, fileTypeOptions, onTogglePreview, statusOptions],
  );
}
