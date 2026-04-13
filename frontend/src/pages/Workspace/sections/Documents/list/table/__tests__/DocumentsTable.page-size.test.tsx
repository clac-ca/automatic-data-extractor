import { useMemo } from "react";
import userEvent from "@testing-library/user-event";
import type { ColumnDef } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";

import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { uiStorageKeys } from "@/lib/uiStorageKeys";
import { render, screen, waitFor } from "@/test/test-utils";
import { useDataTable } from "@/hooks/use-data-table";

import { useDocumentsListParams } from "../../hooks/useDocumentsListParams";
import { useDocumentsPageSizePreference } from "../../hooks/useDocumentsPageSizePreference";
import { DOCUMENTS_PAGE_SIZE_OPTIONS } from "../../../shared/constants";

type RowData = {
  id: string;
  name: string;
};

function PageSizeHarness() {
  const columns = useMemo<ColumnDef<RowData>[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        header: "Name",
      },
    ],
    [],
  );
  const { defaultPageSize, setPageSizePreference } = useDocumentsPageSizePreference("ws-1");
  const { perPage } = useDocumentsListParams({ defaultPerPage: defaultPageSize });
  const { table } = useDataTable({
    data: [{ id: "doc-1", name: "Doc 1" }],
    columns,
    pageCount: 1,
    initialState: {
      pagination: { pageIndex: 0, pageSize: defaultPageSize },
    },
    getRowId: (row) => row.id,
  });

  return (
    <div>
      <div data-testid="query-per-page">{perPage}</div>
      <div data-testid="table-page-size">{table.getState().pagination.pageSize}</div>
      <DataTablePagination
        table={table}
        pageSizeOptions={DOCUMENTS_PAGE_SIZE_OPTIONS}
        onPageSizeChange={setPageSizePreference}
      />
    </div>
  );
}

describe("documents rows-per-page persistence", () => {
  it("restores the remembered page size when remounting without a perPage query param", async () => {
    window.localStorage.clear();

    const user = userEvent.setup();
    const firstRender = render(<PageSizeHarness />, { route: "/workspaces/ws-1/documents" });

    expect(screen.getByTestId("query-per-page")).toHaveTextContent("100");
    expect(screen.getByTestId("table-page-size")).toHaveTextContent("100");

    const trigger = document.querySelector("[data-slot='select-trigger']");
    expect(trigger).not.toBeNull();

    await user.click(trigger as HTMLElement);
    await user.click(await screen.findByRole("option", { name: "500" }));

    await waitFor(() => {
      expect(screen.getByTestId("query-per-page")).toHaveTextContent("500");
    });
    expect(screen.getByTestId("table-page-size")).toHaveTextContent("500");
    expect(window.localStorage.getItem(uiStorageKeys.documentsRowsPerPage("ws-1"))).toBe(
      JSON.stringify(500),
    );

    firstRender.unmount();

    render(<PageSizeHarness />, { route: "/workspaces/ws-1/documents" });

    expect(screen.getByTestId("query-per-page")).toHaveTextContent("500");
    expect(screen.getByTestId("table-page-size")).toHaveTextContent("500");
  });
});
