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

    expect(putSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspace_id}/default", {
      params: { path: { workspace_id: "ws-123" } },
    });
  });

  it("clamps member pagination to the API max", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [], page: 1, page_size: MAX_PAGE_SIZE, has_next: false, has_previous: false, total: 0 },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listWorkspaceMembers("ws-123", { pageSize: 500 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspace_id}/members", {
      params: { path: { workspace_id: "ws-123" }, query: { page_size: MAX_PAGE_SIZE } },
      signal: undefined,
    });
  });

  it("requests workspace roles with a clamped page size", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [], page: 1, page_size: MAX_PAGE_SIZE, has_next: false, has_previous: false, total: 0 },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listWorkspaceRoles({ pageSize: 250 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/rbac/roles", {
      params: { query: { scope: "workspace", page_size: MAX_PAGE_SIZE } },
      signal: undefined,
    });
  });

  it("requests workspace permissions scoped to the workspace with a clamped page size", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: { items: [], page: 1, page_size: MAX_PAGE_SIZE, has_next: false, has_previous: false, total: 0 },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listPermissions({ pageSize: 400 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/rbac/permissions", {
      params: { query: { scope: "workspace", page_size: MAX_PAGE_SIZE } },
      signal: undefined,
    });
  });
});
