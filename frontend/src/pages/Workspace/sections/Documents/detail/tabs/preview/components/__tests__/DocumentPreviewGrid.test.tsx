import type { ComponentProps } from "react";
import { act } from "react";
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
  getLuminance: (color: string) => (color === "#ffffff" || color === "#e6f5f5" ? 1 : 0),
  GridCellKind: {
    Text: "text",
  },
  textCellRenderer: {
    kind: "text",
    draw: vi.fn(),
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
      rowNumbers={[1, 3]}
      columnLabels={["A", "B", "C"]}
      cellFormats={[]}
      {...overrides}
    />,
  );
}

describe("DocumentPreviewGrid", () => {
  beforeEach(() => {
    dataEditorMock.mockClear();
    useGlideDataEditorThemeMock.mockClear();
  });

  it("renders Glide DataEditor with spreadsheet editing defaults", () => {
    renderGrid();

    expect(screen.getByTestId("preview-grid-editor")).toBeInTheDocument();

    const latestCall = dataEditorMock.mock.calls.at(-1);
    const props = latestCall?.[0] as Record<string, unknown>;

    expect(props.rows).toBe(50);
    expect(props.columns).toHaveLength(27);
    expect(props.freezeColumns).toBe(1);
    expect(props.rangeSelect).toBe("multi-rect");
    expect(props.rowSelect).toBe("none");
    expect(props.columnSelect).toBe("multi");
    expect(props.drawFocusRing).toBe(true);
    expect(props.scrollToActiveCell).toBe(true);
    expect(props.cellActivationBehavior).toBe("double-click");
    expect(props.onPaste).toBe(true);
    expect(props.editOnType).toBe(true);
    expect(props.onCellEdited).toEqual(expect.any(Function));
    expect(props.getCellsForSelection).toBe(true);
    expect(props.renderers).toHaveLength(1);
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
        cellHorizontalPadding: 8,
        cellVerticalPadding: 2,
        bgHeader: "#f1f3f4",
      }),
    );
  });

  it("maps preview rows and worksheet padding to editable text cells", () => {
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

    const firstRowMarker = props.getCellContent([0, 0]);
    const secondRowMarker = props.getCellContent([0, 1]);
    const firstCell = props.getCellContent([1, 0]);
    const secondColumnCell = props.getCellContent([2, 0]);
    const emptySheetCell = props.getCellContent([26, 49]);

    expect(firstRowMarker.data).toBe("1");
    expect(secondRowMarker.data).toBe("3");
    expect(firstCell).toEqual(
      expect.objectContaining({
        kind: "text",
        data: "A1",
        displayData: "A1",
        allowOverlay: true,
        readonly: false,
      }),
    );
    expect(secondColumnCell.data).toBe("B1");
    expect(emptySheetCell.data).toBe("");
  });

  it("stores edits locally without editing the row-number column", () => {
    renderGrid();

    const latestCall = dataEditorMock.mock.calls.at(-1);
    const props = latestCall?.[0] as {
      getCellContent: (cell: [number, number]) => { data: string; readonly: boolean };
      onCellEdited: (cell: [number, number], newValue: { kind: string; data: string }) => void;
    };

    act(() => {
      props.onCellEdited([2, 0], { kind: "text", data: "Edited B1" });
      props.onCellEdited([0, 0], { kind: "text", data: "99" });
    });

    const updatedProps = dataEditorMock.mock.calls.at(-1)?.[0] as typeof props;
    expect(updatedProps.getCellContent([2, 0]).data).toBe("Edited B1");
    expect(updatedProps.getCellContent([0, 0])).toEqual(
      expect.objectContaining({
        data: "1",
        readonly: true,
      }),
    );
  });

  it("applies Excel-style cell formatting metadata", () => {
    renderGrid({
      cellFormats: [
        {
          row: 0,
          column: 1,
          bgColor: "#008000",
          textColor: "#ffffff",
          bold: true,
          italic: true,
          horizontalAlign: "center",
          wrapText: true,
        },
      ],
    });

    const latestCall = dataEditorMock.mock.calls.at(-1);
    const props = latestCall?.[0] as {
      getCellContent: (cell: [number, number]) => {
        allowWrapping?: boolean;
        contentAlign?: string;
        themeOverride?: Record<string, string | undefined>;
      };
    };

    const formattedCell = props.getCellContent([2, 0]);

    expect(formattedCell).toEqual(
      expect.objectContaining({
        allowWrapping: true,
        contentAlign: "center",
        themeOverride: expect.objectContaining({
          bgCell: "#008000",
          textDark: "#ffffff",
          baseFontStyle: "italic 700 12px Inter, sans-serif",
        }),
      }),
    );
  });

  it("shows empty state when no preview rows are available", () => {
    renderGrid({ rows: [] });

    expect(screen.getByText("No rows available in the preview.")).toBeInTheDocument();
    expect(screen.queryByTestId("preview-grid-editor")).not.toBeInTheDocument();
  });
});
