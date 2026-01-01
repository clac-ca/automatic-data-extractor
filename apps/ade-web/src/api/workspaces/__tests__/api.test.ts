import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@api/client";
import { MAX_PAGE_SIZE } from "@api/pagination";
import { listPermissions, listWorkspaceMembers, listWorkspaceRoles, setDefaultWorkspace } from "../api";

describe("workspaces api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("issues a PUT to mark the default workspace", async () => {
    const putSpy = vi
      .spyOn(client, "PUT")
      .mockResolvedValue({ data: undefined } as Awaited<ReturnType<typeof client.PUT>>);

    await setDefaultWorkspace("ws-123");

    expect(putSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/default", {
      params: { path: { workspaceId: "ws-123" } },
    });
  });

  it("clamps member pagination to the API max", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [], page: 1, perPage: MAX_PAGE_SIZE, pageCount: 1, total: 0, changesCursor: "0" },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listWorkspaceMembers("ws-123", { pageSize: 500 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/members", {
      params: { path: { workspaceId: "ws-123" }, query: { perPage: MAX_PAGE_SIZE } },
      signal: undefined,
    });
  });

  it("requests workspace roles with a clamped page size", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [], page: 1, perPage: MAX_PAGE_SIZE, pageCount: 1, total: 0, changesCursor: "0" },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listWorkspaceRoles({ pageSize: 250 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/roles", {
      params: {
        query: {
          perPage: MAX_PAGE_SIZE,
          filters: JSON.stringify([{ id: "scopeType", operator: "eq", value: "workspace" }]),
        },
      },
      signal: undefined,
    });
  });

  it("requests workspace permissions scoped to the workspace with a clamped page size", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [], page: 1, perPage: MAX_PAGE_SIZE, pageCount: 1, total: 0, changesCursor: "0" },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listPermissions({ pageSize: 400 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/permissions", {
      params: {
        query: {
          perPage: MAX_PAGE_SIZE,
          filters: JSON.stringify([{ id: "scopeType", operator: "eq", value: "workspace" }]),
        },
      },
      signal: undefined,
    });
  });
});
