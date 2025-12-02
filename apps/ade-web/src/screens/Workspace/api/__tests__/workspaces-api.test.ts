import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shared/api/client";
import { setDefaultWorkspace } from "../workspaces-api";

describe("workspaces-api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("issues a PUT to mark the default workspace", async () => {
    const putSpy = vi.spyOn(client, "PUT").mockResolvedValue({ data: undefined } as unknown as object);

    await setDefaultWorkspace("ws-123");

    expect(putSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspace_id}/default", {
      params: { path: { workspace_id: "ws-123" } },
    });
  });
});
