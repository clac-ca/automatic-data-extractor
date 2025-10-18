import { describe, expect, it } from "vitest";

import { normaliseStatusFilter } from "../api";

describe("normaliseStatusFilter", () => {
  it("returns undefined when the status is empty", () => {
    expect(normaliseStatusFilter(undefined)).toBeUndefined();
    expect(normaliseStatusFilter(null)).toBeUndefined();
    expect(normaliseStatusFilter([])).toBeUndefined();
  });

  it("wraps a single status value in an array", () => {
    expect(normaliseStatusFilter("uploaded")).toEqual(["uploaded"]);
  });

  it("returns the provided array when multiple statuses are supplied", () => {
    expect(normaliseStatusFilter(["uploaded", "processed"])).toEqual(["uploaded", "processed"]);
  });
});
