import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

const dataEditorMock = vi.fn();
const useGlideDataEditorThemeMock = vi.fn(() => ({
  accentColor: "#123456",
  bgCell: "#101112",
  textDark: "#f8f9fa",
}));

vi.mock("@/providers/theme/glideTheme", () => ({
  useGlideDataEditorTheme: () => useGlideDataEditorThemeMock(),
}));

vi.mock("@glideapps/glide-data-grid", () => ({
  GridCellKind: {
    Text: "text",
  },
  DataEditor: (props: unknown) => {
    dataEditorMock(props);
    return <div data-testid="preview-grid-editor" />;
  },
}));

import { DocumentPreviewGrid } from "../DocumentPreviewGrid";

function renderGrid(overrides: Partial<ComponentProps<typeof DocumentPreviewGrid>> = {}) {
  return render(
    <DocumentPreviewGrid
      hasSheetError={false}
      hasPreviewError={false}
      isLoading={false}
      hasSheets
      hasData
      rows={[
        ["A1", "B1", "C1"],
        ["A2", "B2", "C2"],
      ]}
      columnLabels={["A", "B", "C"]}
      {...overrides}
    />,
  );
}

describe("DocumentPreviewGrid", () => {
  beforeEach(() => {
    dataEditorMock.mockClear();
    useGlideDataEditorThemeMock.mockClear();
  });

  it("renders Glide DataEditor with compact, read-only defaults", () => {
    renderGrid();

    expect(screen.getByTestId("preview-grid-editor")).toBeInTheDocument();

    const latestCall = dataEditorMock.mock.calls.at(-1);
    const props = latestCall?.[0] as Record<string, unknown>;

    expect(props.rowMarkers).toEqual(
      expect.objectContaining({
        kind: "number",
        startIndex: 1,
      }),
    );
    expect(props.getCellsForSelection).toBe(true);
    expect(props.smoothScrollX).toBe(true);
    expect(props.smoothScrollY).toBe(true);
    expect(props.fixedShadowX).toBe(true);
    expect(props.fixedShadowY).toBe(true);
    expect(useGlideDataEditorThemeMock).toHaveBeenCalledTimes(1);
    expect(props.theme).toEqual(
      expect.objectContaining({
        accentColor: "#123456",
        bgCell: "#101112",
        textDark: "#f8f9fa",
        baseFontStyle: "12px Inter, sans-serif",
        headerFontStyle: "600 11px Inter, sans-serif",
        editorFontSize: "12px",
        cellHorizontalPadding: 6,
        cellVerticalPadding: 2,
      }),
    );
  });

  it("maps preview rows to read-only text cells", () => {
    renderGrid();

    const latestCall = dataEditorMock.mock.calls.at(-1);
    const props = latestCall?.[0] as {
      getCellContent: (cell: [number, number]) => {
        kind: string;
        data: string;
        displayData: string;
        allowOverlay: boolean;
        readonly: boolean;
      };
    };

    const firstCell = props.getCellContent([0, 0]);
    const secondColumnCell = props.getCellContent([1, 0]);

    expect(firstCell).toEqual(
      expect.objectContaining({
        kind: "text",
        data: "A1",
        displayData: "A1",
        allowOverlay: false,
        readonly: true,
      }),
    );
    expect(secondColumnCell.data).toBe("B1");
  });

  it("shows empty state when no preview rows are available", () => {
    renderGrid({ rows: [] });

    expect(screen.getByText("No rows available in the preview.")).toBeInTheDocument();
    expect(screen.queryByTestId("preview-grid-editor")).not.toBeInTheDocument();
  });
});
