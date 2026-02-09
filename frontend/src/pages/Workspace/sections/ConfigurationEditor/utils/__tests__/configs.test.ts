import { describe, expect, it, vi } from "vitest";

import { normalizeConfigStatus, sortByUpdatedDesc, suggestDuplicateName } from "../configs";

describe("ConfigurationEditor config utils", () => {
  it("normalizes configuration status values", () => {
    expect(normalizeConfigStatus(undefined)).toBe("");
    expect(normalizeConfigStatus(null)).toBe("");
    expect(normalizeConfigStatus("Draft")).toBe("draft");
    expect(normalizeConfigStatus(123)).toBe("123");
  });

  it("sorts updated timestamps in descending order", () => {
    expect(sortByUpdatedDesc("2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z")).toBeGreaterThan(0);
    expect(sortByUpdatedDesc("2020-01-02T00:00:00Z", "2020-01-01T00:00:00Z")).toBeLessThan(0);
    expect(sortByUpdatedDesc(null, null)).toBe(0);
    expect(sortByUpdatedDesc(undefined, "2020-01-01T00:00:00Z")).toBeGreaterThan(0);
  });

  it("suggests a unique duplicate name", () => {
    expect(suggestDuplicateName("Foo", new Set())).toBe("Copy of Foo");

    const existing = new Set(["copy of foo"]);
    expect(suggestDuplicateName("Foo", existing)).toBe("Copy of Foo (2)");

    existing.add("copy of foo (2)");
    expect(suggestDuplicateName("Foo", existing)).toBe("Copy of Foo (3)");
  });

  it("falls back to a timestamp when all numbered names are taken", () => {
    const base = "Copy of Foo";
    const existing = new Set<string>([base.toLowerCase()]);
    for (let index = 2; index < 100; index += 1) {
      existing.add(`${base} (${index})`.toLowerCase());
    }

    const now = vi.spyOn(Date, "now").mockReturnValue(123);
    expect(suggestDuplicateName("Foo", existing)).toBe(`${base} (123)`);
    now.mockRestore();
  });
});
