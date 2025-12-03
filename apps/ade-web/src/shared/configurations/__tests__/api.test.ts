import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shared/api/client";
import { createConfigurationDirectory, deleteConfigurationDirectory } from "../api";

describe("configuration directory api helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a directory via PUT and returns the payload", async () => {
    const spy = vi
      .spyOn(client, "PUT")
      .mockResolvedValue(
        { data: { path: "assets/new", created: true } } as unknown as Awaited<
          ReturnType<(typeof client)["PUT"]>
        >,
      );

    const result = await createConfigurationDirectory("ws1", "cfg1", "assets/new");

    expect(result).toEqual({ path: "assets/new", created: true });
    expect(spy).toHaveBeenCalledWith(
      "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}",
      {
        params: {
          path: { workspace_id: "ws1", configuration_id: "cfg1", directory_path: "assets/new" },
        },
      },
    );
  });

  it("deletes a directory with the recursive flag when requested", async () => {
    const spy = vi
      .spyOn(client, "DELETE")
      .mockResolvedValue({} as unknown as Awaited<ReturnType<(typeof client)["DELETE"]>>);

    await deleteConfigurationDirectory("ws1", "cfg1", "assets/new", { recursive: true });

    expect(spy).toHaveBeenCalledWith(
      "/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}",
      {
        params: {
          path: { workspace_id: "ws1", configuration_id: "cfg1", directory_path: "assets/new" },
          query: { recursive: true },
        },
      },
    );
  });
});
