import { describe, expect, it } from "vitest";

import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { getNormalizedPreviewState } from "../state";

function makeDocument(lastRun: DocumentRow["lastRun"]): DocumentRow {
  return {
    id: "doc_1",
    workspaceId: "ws_1",
    name: "test.xlsx",
    fileType: "xlsx",
    byteSize: 10,
    commentCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    tags: [],
    lastRun,
  } as DocumentRow;
}

describe("getNormalizedPreviewState", () => {
  it("is available when latest run succeeded", () => {
    const state = getNormalizedPreviewState(
      makeDocument({
        id: "run_1",
        status: "succeeded",
        createdAt: "2026-01-01T00:00:00Z",
        startedAt: null,
        completedAt: null,
        errorMessage: null,
      }),
    );
    expect(state.available).toBe(true);
    expect(state.reason).toBeNull();
  });

  it("is unavailable when run is in progress", () => {
    const state = getNormalizedPreviewState(
      makeDocument({
        id: "run_1",
        status: "running",
        createdAt: "2026-01-01T00:00:00Z",
        startedAt: null,
        completedAt: null,
        errorMessage: null,
      }),
    );
    expect(state.available).toBe(false);
    expect(state.reason).toContain("not ready");
  });

  it("is unavailable with explicit message when failed", () => {
    const state = getNormalizedPreviewState(
      makeDocument({
        id: "run_1",
        status: "failed",
        createdAt: "2026-01-01T00:00:00Z",
        startedAt: null,
        completedAt: null,
        errorMessage: "Engine crashed",
      }),
    );
    expect(state.available).toBe(false);
    expect(state.reason).toContain("Engine crashed");
  });

  it("is unavailable with cancelled message when latest run was cancelled", () => {
    const state = getNormalizedPreviewState(
      makeDocument({
        id: "run_1",
        status: "cancelled",
        createdAt: "2026-01-01T00:00:00Z",
        startedAt: null,
        completedAt: null,
        errorMessage: "Run cancelled by user",
      }),
    );
    expect(state.available).toBe(false);
    expect(state.reason).toContain("cancelled");
  });
});
