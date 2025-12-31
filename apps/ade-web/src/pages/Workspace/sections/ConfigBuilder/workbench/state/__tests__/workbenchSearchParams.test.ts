import { describe, expect, it } from "vitest";

import { DEFAULT_WORKBENCH_SEARCH, mergeWorkbenchSearchParams, readWorkbenchSearchParams } from "../workbenchSearchParams";

describe("workbenchSearchParams", () => {
  it("parses defaults and presence flags", () => {
    const snapshot = readWorkbenchSearchParams("file=/src/app.ts&console=open&pane=problems&runId=run-123&view=split");

    expect(snapshot.fileId).toBe("/src/app.ts");
    expect(snapshot.console).toBe("open");
    expect(snapshot.pane).toBe("problems");
    expect(snapshot.present).toEqual({
      pane: true,
      console: true,
      fileId: true,
    });
  });

  it("falls back to defaults when values are invalid", () => {
    const snapshot = readWorkbenchSearchParams("pane=unknown&console=nope");

    expect(snapshot.pane).toBe(DEFAULT_WORKBENCH_SEARCH.pane);
    expect(snapshot.console).toBe(DEFAULT_WORKBENCH_SEARCH.console);
    expect(snapshot.present.pane).toBe(true);
  });

  it("ignores unknown parameters", () => {
    const snapshot = readWorkbenchSearchParams("path=/legacy/file.py&run_id=run-456&pane=console");

    expect(snapshot.fileId).toBeUndefined();
    expect(snapshot.pane).toBe(DEFAULT_WORKBENCH_SEARCH.pane);
    expect(snapshot.present.fileId).toBe(false);
  });

  it("merges patches, removes defaults, and strips legacy keys", () => {
    const base = new URLSearchParams("file=/one.ts&console=open&pane=terminal&runId=run-123&view=split");
    const next = mergeWorkbenchSearchParams(base, {
      fileId: undefined,
      pane: "problems",
    });

    expect(next.get("console")).toBe("open");
    expect(next.get("pane")).toBe("problems");
    expect(next.has("file")).toBe(false);
    expect(next.has("runId")).toBe(false);
    expect(next.has("view")).toBe(false);

    const reset = mergeWorkbenchSearchParams(next, { pane: DEFAULT_WORKBENCH_SEARCH.pane, console: "closed" });
    expect(reset.has("pane")).toBe(false);
    expect(reset.has("console")).toBe(false);
  });
});
