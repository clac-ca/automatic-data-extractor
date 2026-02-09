import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import {
  createConfigurationDirectory,
  deleteConfigurationDirectory,
  importConfiguration,
  replaceConfigurationImport,
} from "../api";

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
      "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}",
      {
        params: {
          path: { workspaceId: "ws1", configurationId: "cfg1", directoryPath: "assets/new" },
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
      "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}",
      {
        params: {
          path: { workspaceId: "ws1", configurationId: "cfg1", directoryPath: "assets/new" },
          query: { recursive: true },
        },
      },
    );
  });

  it("routes github imports to the github endpoint", async () => {
    const spy = vi
      .spyOn(client, "POST")
      .mockResolvedValue(
        { data: { id: "cfg1" } } as unknown as Awaited<ReturnType<(typeof client)["POST"]>>,
      );

    await importConfiguration("ws1", {
      type: "github",
      displayName: "Imported configuration",
      url: "https://github.com/octo/repo",
    });

    expect(spy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/configurations/import/github", {
      params: { path: { workspaceId: "ws1" } },
      body: {
        display_name: "Imported configuration",
        url: "https://github.com/octo/repo",
      },
    });
  });

  it("routes github replace imports to the github replace endpoint", async () => {
    const spy = vi
      .spyOn(client, "PUT")
      .mockResolvedValue(
        { data: { id: "cfg1" } } as unknown as Awaited<ReturnType<(typeof client)["PUT"]>>,
      );

    await replaceConfigurationImport("ws1", "cfg1", {
      type: "github",
      url: "https://github.com/octo/repo/tree/main",
      ifMatch: "etag-token",
    });

    expect(spy).toHaveBeenCalledWith(
      "/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import/github",
      {
        params: { path: { workspaceId: "ws1", configurationId: "cfg1" } },
        headers: { "If-Match": "etag-token" },
        body: { url: "https://github.com/octo/repo/tree/main" },
      },
    );
  });
});
