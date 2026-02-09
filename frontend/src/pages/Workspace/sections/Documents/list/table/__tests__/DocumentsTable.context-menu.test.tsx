import { useMemo, useState } from "react";
import { fireEvent } from "@testing-library/react";
import { getCoreRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import type { FilterJoinOperator } from "@/api/listing";
import type { DocumentLifecycle } from "@/api/documents";
import { render, screen } from "@/test/test-utils";

import type { DocumentRow } from "../../../shared/types";
import { DocumentsTable } from "../DocumentsTable";

function makeDocument(): DocumentRow {
  return {
    id: "doc_1",
    workspaceId: "ws_1",
    name: "source.csv",
    fileType: "csv",
    byteSize: 16,
    commentCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    tags: [],
    assignee: null,
    uploader: null,
    lastRun: null,
    lifecycle: "active",
  } as DocumentRow;
}

function TestHarness({
  buildItems,
}: {
  buildItems: (document: DocumentRow) => { id: string; label: string; onSelect: () => void }[];
}) {
  const data = useMemo<DocumentRow[]>(() => [makeDocument()], []);
  const columns = useMemo<ColumnDef<DocumentRow>[]>(
    () => [
      {
        id: "document",
        accessorKey: "name",
        header: "Document",
        cell: ({ row }) => row.original.name,
      },
    ],
    [],
  );

  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState([]);
  const [columnVisibility, setColumnVisibility] = useState({});
  const [rowSelection, setRowSelection] = useState({});
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 20 });

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      pagination,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
    pageCount: 1,
    manualFiltering: true,
    manualSorting: true,
    manualPagination: true,
    meta: {
      filterFields: [],
      joinOperator: "and" as FilterJoinOperator,
      setJoinOperator: vi.fn(),
      lifecycle: "active" as DocumentLifecycle,
      setLifecycle: vi.fn(),
    },
  });

  return (
    <DocumentsTable
      table={table}
      debounceMs={0}
      throttleMs={0}
      shallow={false}
      buildRowContextMenuItems={buildItems}
      onRowActivate={() => {}}
    />
  );
}

describe("DocumentsTable row context menu", () => {
  it("opens custom row context menu on right click", async () => {
    const onOpen = vi.fn();
    render(
      <TestHarness
        buildItems={() => [
          {
            id: "open",
            label: "Open",
            onSelect: onOpen,
          },
        ]}
      />,
    );

    const row = screen.getAllByRole("row")[1];
    fireEvent.contextMenu(row);

    const menuItem = await screen.findByRole("menuitem", { name: "Open" });
    expect(menuItem).toBeInTheDocument();

    fireEvent.click(menuItem);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
