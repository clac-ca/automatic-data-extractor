import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { patchWorkspaceDocument } from "@/api/documents/api";

type PatchResponse = Awaited<ReturnType<(typeof client)["PATCH"]>>;

describe("documents api helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends rename payloads when patching a document", async () => {
    const responsePayload = {
      id: "doc-1",
      workspaceId: "ws-1",
      name: "Quarterly Intake.xlsx",
      byteSize: 123,
      metadata: {},
      tags: [],
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      activityAt: "2026-01-01T00:00:00Z",
      fileType: "xlsx",
    };

    const spy = vi.spyOn(client, "PATCH").mockResolvedValue(
      { data: responsePayload } as unknown as PatchResponse,
    );

    const result = await patchWorkspaceDocument("ws-1", "doc-1", {
      name: "Quarterly Intake.xlsx",
    });

    expect(result).toEqual(responsePayload);
    expect(spy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/documents/{documentId}", {
      params: { path: { workspaceId: "ws-1", documentId: "doc-1" } },
      body: { name: "Quarterly Intake.xlsx" },
    });
  });

  it("throws when patching does not return a document", async () => {
    vi.spyOn(client, "PATCH").mockResolvedValue(
      { data: undefined } as unknown as PatchResponse,
    );

    await expect(
      patchWorkspaceDocument("ws-1", "doc-1", { name: "Renamed.xlsx" }),
    ).rejects.toThrow("Expected updated document record.");
  });
});
