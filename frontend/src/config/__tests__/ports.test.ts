import { describe, expect, it } from "vitest";

import { DEFAULT_WEB_PORT, parsePortFromEnv } from "../ports";

describe("parsePortFromEnv", () => {
  it("returns fallback when value is undefined", () => {
    expect(
      parsePortFromEnv(undefined, {
        envVar: "ADE_WEB_PORT",
        fallback: DEFAULT_WEB_PORT,
      }),
    ).toBe(DEFAULT_WEB_PORT);
  });

  it("parses a valid integer", () => {
    expect(
      parsePortFromEnv("31234", {
        envVar: "ADE_WEB_PORT",
        fallback: DEFAULT_WEB_PORT,
      }),
    ).toBe(31234);
  });

  it("throws for invalid integer values", () => {
    expect(() =>
      parsePortFromEnv("not-a-port", {
        envVar: "ADE_WEB_PORT",
        fallback: DEFAULT_WEB_PORT,
      }),
    ).toThrow("ADE_WEB_PORT");
  });
});

