import { useMemo, useState } from "react";
import { fireEvent } from "@testing-library/react";
import {
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnFiltersState,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

import { DataTable } from "../data-table";

type RowData = {
  id: string;
  name: string;
};

function TestHarness({
  onActivate,
  onContext,
}: {
  onActivate: (id: string) => void;
  onContext: (id: string) => void;
}) {
  const data = useMemo<RowData[]>(() => [{ id: "doc_1", name: "Doc 1" }], []);
  const columns = useMemo<ColumnDef<RowData>[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => (
          <div>
            <span>{row.original.name}</span>
            <button type="button">Inner action</button>
            <div role="option" aria-selected="false" data-row-interactive>
              Faceted option
            </div>
          </div>
        ),
      },
    ],
    [],
  );

  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 20 });

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
  });

  return (
    <DataTable
      table={table}
      onRowActivate={(row) => {
        onActivate(row.original.id);
      }}
      onRowContextMenu={(row) => {
        onContext(row.original.id);
      }}
    />
  );
}

describe("DataTable", () => {
  it("activates row click but ignores interactive elements", () => {
    const onActivate = vi.fn();
    const onContext = vi.fn();
    render(<TestHarness onActivate={onActivate} onContext={onContext} />);

    const row = screen.getByText("Doc 1").closest("tr");
    expect(row).not.toBeNull();

    fireEvent.click(row as HTMLElement);
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onActivate).toHaveBeenCalledWith("doc_1");

    fireEvent.click(screen.getByRole("button", { name: "Inner action" }));
    fireEvent.click(screen.getByRole("option", { name: "Faceted option" }));
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onContext).toHaveBeenCalledTimes(0);
  });

  it("supports keyboard row activation", () => {
    const onActivate = vi.fn();
    const onContext = vi.fn();
    render(<TestHarness onActivate={onActivate} onContext={onContext} />);

    const row = screen.getByText("Doc 1").closest("tr");
    expect(row).not.toBeNull();

    fireEvent.keyDown(row as HTMLElement, { key: "Enter" });
    fireEvent.keyDown(row as HTMLElement, { key: " " });

    expect(onActivate).toHaveBeenCalledTimes(2);
    expect(onActivate).toHaveBeenNthCalledWith(1, "doc_1");
    expect(onActivate).toHaveBeenNthCalledWith(2, "doc_1");
    expect(onContext).toHaveBeenCalledTimes(0);
  });

  it("supports row context menu and ignores interactive targets", () => {
    const onActivate = vi.fn();
    const onContext = vi.fn();
    render(<TestHarness onActivate={onActivate} onContext={onContext} />);

    const row = screen.getByText("Doc 1").closest("tr");
    expect(row).not.toBeNull();

    fireEvent.contextMenu(row as HTMLElement);
    expect(onContext).toHaveBeenCalledTimes(1);
    expect(onContext).toHaveBeenLastCalledWith("doc_1");

    fireEvent.contextMenu(screen.getByRole("button", { name: "Inner action" }));
    expect(onContext).toHaveBeenCalledTimes(1);
  });

  it("opens row context menu even after prior interactive pointer intent", () => {
    const onActivate = vi.fn();
    const onContext = vi.fn();
    render(<TestHarness onActivate={onActivate} onContext={onContext} />);

    const row = screen.getByText("Doc 1").closest("tr");
    expect(row).not.toBeNull();

    fireEvent.pointerDown(screen.getByRole("button", { name: "Inner action" }));
    fireEvent.contextMenu(row as HTMLElement);

    expect(onContext).toHaveBeenCalledTimes(1);
    expect(onActivate).toHaveBeenCalledTimes(0);
  });

  it("supports keyboard row context menu", () => {
    const onActivate = vi.fn();
    const onContext = vi.fn();
    render(<TestHarness onActivate={onActivate} onContext={onContext} />);

    const row = screen.getByText("Doc 1").closest("tr");
    expect(row).not.toBeNull();

    fireEvent.keyDown(row as HTMLElement, { key: "ContextMenu" });
    fireEvent.keyDown(row as HTMLElement, { key: "F10", shiftKey: true });

    expect(onContext).toHaveBeenCalledTimes(2);
    expect(onContext).toHaveBeenNthCalledWith(1, "doc_1");
    expect(onContext).toHaveBeenNthCalledWith(2, "doc_1");
    expect(onActivate).toHaveBeenCalledTimes(0);
  });
});
