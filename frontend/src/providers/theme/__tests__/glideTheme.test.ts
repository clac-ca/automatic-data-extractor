import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const resolveCssRgbaColorMock = vi.fn((_: string, fallback: string) => fallback);

const themeState: { theme: string; resolvedMode: "light" | "dark" } = {
  theme: "default",
  resolvedMode: "light",
};

vi.mock("@/providers/theme", () => ({
  useTheme: () => ({
    theme: themeState.theme,
    resolvedMode: themeState.resolvedMode,
  }),
}));

vi.mock("../cssColor", () => ({
  resolveCssRgbaColor: (variable: string, fallback: string) => resolveCssRgbaColorMock(variable, fallback),
}));

import { useGlideDataEditorTheme } from "../glideTheme";

describe("useGlideDataEditorTheme", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    themeState.theme = "default";
    themeState.resolvedMode = "light";
  });

  it("falls back to defaults when CSS token resolution is unavailable", () => {
    resolveCssRgbaColorMock.mockImplementation((_: string, fallback: string) => fallback);

    const { result } = renderHook(() => useGlideDataEditorTheme());

    expect(result.current.accentColor).toBe("#4F5DFF");
    expect(result.current.bgCell).toBe("#FFFFFF");
    expect(result.current.borderColor).toBe("rgba(115, 116, 131, 0.16)");
    expect(result.current.linkColor).toBe("#353fb5");
  });

  it("recomputes palette when theme id or resolved mode changes", () => {
    let currentPrimary = "rgb(11, 22, 33)";
    resolveCssRgbaColorMock.mockImplementation((variable: string, fallback: string) => {
      if (variable === "--primary") {
        return currentPrimary;
      }
      return fallback;
    });

    const { result, rerender } = renderHook(() => useGlideDataEditorTheme());
    expect(result.current.accentColor).toBe("rgb(11, 22, 33)");

    currentPrimary = "rgb(44, 55, 66)";
    themeState.theme = "blue";
    rerender();
    expect(result.current.accentColor).toBe("rgb(44, 55, 66)");

    currentPrimary = "rgb(77, 88, 99)";
    themeState.resolvedMode = "dark";
    rerender();
    expect(result.current.accentColor).toBe("rgb(77, 88, 99)");
  });
});
