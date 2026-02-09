import { describe, expect, it } from "vitest";

import { isValidUuidFilter } from "../pages/ApiKeysSettingsPage";

describe("isValidUuidFilter", () => {
  it("accepts canonical UUID values", () => {
    expect(isValidUuidFilter("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
  });

  it("rejects invalid UUID values", () => {
    expect(isValidUuidFilter("not-a-uuid")).toBe(false);
    expect(isValidUuidFilter("550e8400e29b41d4a716446655440000")).toBe(false);
  });
});
