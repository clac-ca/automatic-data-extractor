import { describe, expect, it } from "vitest";

import {
  buildDocumentDetailUrl,
  getDocumentDetailState,
} from "../navigation";

describe("document detail navigation", () => {
  it("defaults to activity tab state", () => {
    const state = getDocumentDetailState(new URLSearchParams());
    expect(state.tab).toBe("activity");
    expect(state.activityFilter).toBe("all");
    expect(state.source).toBe("normalized");
    expect(state.sheet).toBeNull();
  });

  it("uses activity defaults for unknown tab values", () => {
    const state = getDocumentDetailState(
      new URLSearchParams("tab=unknown&activityFilter=bad"),
    );
    expect(state.tab).toBe("activity");
    expect(state.activityFilter).toBe("all");
  });

  it("builds preview links with source and sheet", () => {
    const url = buildDocumentDetailUrl("ws_1", "doc_1", {
      tab: "preview",
      source: "original",
      sheet: "January",
    });
    expect(url).toBe(
      "/workspaces/ws_1/documents/doc_1?tab=preview&source=original&sheet=January",
    );
  });

  it("builds activity links without default filters", () => {
    const url = buildDocumentDetailUrl("ws_1", "doc_1", {
      tab: "activity",
      activityFilter: "all",
    });
    expect(url).toBe("/workspaces/ws_1/documents/doc_1?tab=activity");
  });
});
