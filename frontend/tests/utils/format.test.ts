import { describe, expect, it } from "vitest";

import { formatBytes, formatDateTime } from "@utils/format";

describe("formatBytes", () => {
  it("formats small values", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  it("formats larger values with units", () => {
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5 MB");
  });

  it("guards against invalid values", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(Number.NaN)).toBe("0 B");
  });
});

describe("formatDateTime", () => {
  it("returns locale string for valid dates", () => {
    const value = "2024-01-01T12:00:00Z";
    const formatted = formatDateTime(value);
    expect(typeof formatted).toBe("string");
    expect(formatted.length).toBeGreaterThan(0);
  });

  it("returns original input for invalid dates", () => {
    expect(formatDateTime("invalid-date"))
      .toBe("invalid-date");
  });
});
