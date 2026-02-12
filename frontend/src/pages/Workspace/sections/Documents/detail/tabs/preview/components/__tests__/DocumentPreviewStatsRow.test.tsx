import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

import { DocumentPreviewStatsRow } from "../DocumentPreviewStatsRow";

describe("DocumentPreviewStatsRow", () => {
  it("renders one meta row with compact checkbox, counts, and up to three inline run metrics", () => {
    render(
      <DocumentPreviewStatsRow
        previewCountSummary={{
          totalRowsLabel: "93 rows",
          totalColumnsLabel: "102 columns",
          rowsVisibleLabel: "Showing 65 of 93 rows",
          columnsVisibleLabel: "Showing first 102 columns",
          hasReduction: true,
        }}
        isCompactMode
        onCompactModeChange={vi.fn()}
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

    expect(screen.getByRole("checkbox", { name: "Hide empty rows and columns" })).toBeChecked();
    expect(screen.getByText("93 rows")).toBeInTheDocument();
    expect(screen.getByText("102 columns")).toBeInTheDocument();
    expect(screen.getByText("Showing 65 of 93 rows")).toBeInTheDocument();
    expect(screen.getByText("Showing first 102 columns")).toBeInTheDocument();
    expect(screen.getByText("Mapped columns:")).toBeInTheDocument();
    expect(screen.getByText("8/10 (80%)")).toBeInTheDocument();
    expect(screen.getByText("Validation issues:")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Non-empty rows:")).toBeInTheDocument();
    expect(screen.getByText("80/100 (80%)")).toBeInTheDocument();
  });

  it("toggles compact mode with one interaction", async () => {
    const user = userEvent.setup();
    const onCompactModeChange = vi.fn();

    render(
      <DocumentPreviewStatsRow
        previewCountSummary={null}
        isCompactMode
        onCompactModeChange={onCompactModeChange}
        metrics={null}
      />,
    );

    await user.click(screen.getByRole("checkbox", { name: "Hide empty rows and columns" }));

    expect(onCompactModeChange).toHaveBeenCalledWith(false);
  });

  it("omits metric pills when no metrics are available while preserving summary and controls", () => {
    render(
      <DocumentPreviewStatsRow
        previewCountSummary={{
          totalRowsLabel: "12 rows",
          totalColumnsLabel: "8 columns",
          rowsVisibleLabel: null,
          columnsVisibleLabel: null,
          hasReduction: false,
        }}
        isCompactMode={false}
        onCompactModeChange={vi.fn()}
        metrics={null}
      />,
    );

    expect(screen.getByRole("checkbox", { name: "Hide empty rows and columns" })).not.toBeChecked();
    expect(screen.getByText("12 rows")).toBeInTheDocument();
    expect(screen.getByText("8 columns")).toBeInTheDocument();
    expect(screen.queryByText("Mapped columns:")).not.toBeInTheDocument();
    expect(screen.queryByText("Validation issues:")).not.toBeInTheDocument();
    expect(screen.queryByText("Non-empty rows:")).not.toBeInTheDocument();
  });
});
