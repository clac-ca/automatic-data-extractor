import { describe, expect, it } from "vitest";

import { resolveVisibleColumnCount } from "../hooks/useDocumentPreviewModel";

describe("resolveVisibleColumnCount", () => {
  it("uses returned preview width when rows are present", () => {
    expect(resolveVisibleColumnCount([["a", "b"], ["c"]], 200)).toBe(2);
  });

  it("caps total column count by max preview columns when rows are empty", () => {
    expect(resolveVisibleColumnCount([], 200)).toBe(50);
  });

  it("keeps smaller total column counts when rows are empty", () => {
    expect(resolveVisibleColumnCount([], 8)).toBe(8);
  });
});
