import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

import { DocumentPreviewStatsRow } from "../DocumentPreviewStatsRow";

describe("DocumentPreviewStatsRow", () => {
  it("renders one meta row with source, hidden-row controls, and inline run metrics", () => {
    render(
      <DocumentPreviewStatsRow
        source="normalized"
        onSourceChange={vi.fn()}
        showHiddenRowsAndColumns
        onShowHiddenRowsAndColumnsChange={vi.fn()}
        metrics={{
          column_count_total: 10,
          column_count_mapped: 8,
          validation_issues_total: 3,
          validation_issues_error: 1,
          row_count_total: 100,
          row_count_empty: 20,
        }}
      />,
    );

    expect(screen.getByRole("checkbox", { name: "Show hidden rows and columns" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Normalized" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Original" })).toBeInTheDocument();
    expect(screen.getByText("Mapped columns:")).toBeInTheDocument();
    expect(screen.getByText("8/10 (80%)")).toBeInTheDocument();
    expect(screen.getByText("Validation issues:")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Non-empty rows:")).toBeInTheDocument();
    expect(screen.getByText("80/100 (80%)")).toBeInTheDocument();
  });

  it("renders correct mapped columns ratio when column_count_empty is specified", () => {
    render(
      <DocumentPreviewStatsRow
        source="normalized"
        onSourceChange={vi.fn()}
        showHiddenRowsAndColumns={false}
        onShowHiddenRowsAndColumnsChange={vi.fn()}
        metrics={{
          column_count_total: 10,
          column_count_empty: 2,
          column_count_mapped: 4,
          validation_issues_total: 0,
        }}
      />,
    );

    expect(screen.getByText("Mapped columns:")).toBeInTheDocument();
    expect(screen.getByText("4/8 (50%)")).toBeInTheDocument();
  });

  it("toggles hidden row and column visibility with one interaction", async () => {
    const user = userEvent.setup();
    const onShowHiddenRowsAndColumnsChange = vi.fn();

    render(
      <DocumentPreviewStatsRow
        source="normalized"
        onSourceChange={vi.fn()}
        showHiddenRowsAndColumns
        onShowHiddenRowsAndColumnsChange={onShowHiddenRowsAndColumnsChange}
        metrics={null}
      />,
    );

    await user.click(screen.getByRole("checkbox", { name: "Show hidden rows and columns" }));

    expect(onShowHiddenRowsAndColumnsChange).toHaveBeenCalledWith(false);
  });

  it("omits metric pills when no metrics are available while preserving controls", () => {
    render(
      <DocumentPreviewStatsRow
        source="original"
        onSourceChange={vi.fn()}
        showHiddenRowsAndColumns={false}
        onShowHiddenRowsAndColumnsChange={vi.fn()}
        metrics={null}
      />,
    );

    expect(screen.getByRole("checkbox", { name: "Show hidden rows and columns" })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Normalized" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Original" })).toBeInTheDocument();
    expect(screen.queryByText("Mapped columns:")).not.toBeInTheDocument();
    expect(screen.queryByText("Validation issues:")).not.toBeInTheDocument();
    expect(screen.queryByText("Non-empty rows:")).not.toBeInTheDocument();
  });
});
