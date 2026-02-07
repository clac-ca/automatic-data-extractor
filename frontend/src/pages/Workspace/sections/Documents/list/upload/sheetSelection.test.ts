import { describe, expect, it } from "vitest";

import {
  buildUploadRunOptions,
  normalizeSheetNames,
  supportsWorkbookSheetSelection,
} from "./sheetSelection";

describe("sheetSelection", () => {
  it("detects workbook file types that support worksheet selection", () => {
    expect(supportsWorkbookSheetSelection("xlsx")).toBe(true);
    expect(supportsWorkbookSheetSelection("xls")).toBe(true);
    expect(supportsWorkbookSheetSelection("csv")).toBe(false);
    expect(supportsWorkbookSheetSelection("pdf")).toBe(false);
  });

  it("normalizes worksheet names", () => {
    expect(normalizeSheetNames([" Summary ", "Detail", "", "Summary", "  "])).toEqual([
      "Summary",
      "Detail",
    ]);
  });

  it("builds run options for active-sheet mode", () => {
    expect(buildUploadRunOptions("active", ["Summary"])).toEqual({
      active_sheet_only: true,
    });
  });

  it("builds run options for all-sheets mode", () => {
    expect(buildUploadRunOptions("all", ["Summary"])).toEqual({
      active_sheet_only: false,
    });
  });

  it("builds run options for selected-sheet mode", () => {
    expect(buildUploadRunOptions("selected", [" Summary ", "Detail", "Summary"])).toEqual({
      active_sheet_only: false,
      input_sheet_names: ["Summary", "Detail"],
    });
  });

  it("falls back to active-sheet mode when selected mode has no sheets", () => {
    expect(buildUploadRunOptions("selected", ["", "  "])).toEqual({
      active_sheet_only: true,
    });
  });
});
