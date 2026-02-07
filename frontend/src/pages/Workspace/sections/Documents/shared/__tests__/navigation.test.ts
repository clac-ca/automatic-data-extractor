import { describe, expect, it } from "vitest";

import {
  buildDocumentDetailUrl,
  getDocumentDetailState,
  normalizeLegacyDocumentDetailSearch,
} from "../navigation";

describe("document detail navigation", () => {
  it("defaults to activity tab state", () => {
    const state = getDocumentDetailState(new URLSearchParams());
    expect(state.tab).toBe("activity");
    expect(state.activityFilter).toBe("all");
    expect(state.source).toBe("normalized");
    expect(state.sheet).toBeNull();
  });

  it("maps legacy comment tab into activity filter", () => {
    const state = getDocumentDetailState(
      new URLSearchParams("tab=comments"),
    );
    expect(state.tab).toBe("activity");
    expect(state.activityFilter).toBe("comments");
    expect(state.usesLegacyTab).toBe(true);
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

  it("normalizes legacy timeline tab params", () => {
    const normalized = normalizeLegacyDocumentDetailSearch(
      new URLSearchParams("tab=timeline"),
    );
    expect(normalized?.toString()).toBe("tab=activity&activityFilter=events");
  });
});
