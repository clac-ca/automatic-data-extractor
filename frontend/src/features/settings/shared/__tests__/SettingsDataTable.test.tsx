import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsDataTable } from "../SettingsDataTable";

type Row = {
  id: string;
  name: string;
};

const rows: Row[] = [
  { id: "1", name: "Alpha" },
  { id: "2", name: "Beta" },
  { id: "3", name: "Gamma" },
];

describe("SettingsDataTable", () => {
  it("opens rows on click and keyboard activation", () => {
    const onRowOpen = vi.fn();

    render(
      <SettingsDataTable
        rows={rows}
        columns={[
          {
            id: "name",
            header: "Name",
            cell: (row) => row.name,
          },
        ]}
        getRowId={(row) => row.id}
        onRowOpen={onRowOpen}
        page={1}
        pageSize={25}
        totalCount={rows.length}
        onPageChange={() => undefined}
        onPageSizeChange={() => undefined}
      />, 
    );

    const alphaCell = screen.getByText("Alpha");
    fireEvent.click(alphaCell);
    expect(onRowOpen).toHaveBeenCalledWith(rows[0]);

    const betaRow = screen.getByText("Beta").closest("tr");
    expect(betaRow).not.toBeNull();
    fireEvent.keyDown(betaRow as HTMLElement, { key: "Enter" });
    fireEvent.keyDown(betaRow as HTMLElement, { key: " " });

    expect(onRowOpen).toHaveBeenCalledWith(rows[1]);
    expect(onRowOpen).toHaveBeenCalledTimes(3);
  });

  it("supports paging controls", () => {
    const onPageChange = vi.fn();

    render(
      <SettingsDataTable
        rows={rows}
        columns={[
          {
            id: "name",
            header: "Name",
            cell: (row) => row.name,
          },
        ]}
        getRowId={(row) => row.id}
        page={2}
        pageSize={1}
        totalCount={rows.length}
        onPageChange={onPageChange}
        onPageSizeChange={() => undefined}
      />, 
    );

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(onPageChange).toHaveBeenNthCalledWith(1, 1);
    expect(onPageChange).toHaveBeenNthCalledWith(2, 3);
  });
});
