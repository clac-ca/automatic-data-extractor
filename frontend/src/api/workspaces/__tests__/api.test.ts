import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { MAX_PAGE_SIZE } from "@/api/pagination";
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

  it("lists workspace principals from role assignments", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        items: [],
        meta: {
          limit: 50,
          hasMore: false,
          nextCursor: null,
          totalIncluded: false,
          totalCount: null,
          changesCursor: "0",
        },
        facets: null,
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listWorkspaceMembers("ws-123", { limit: 500 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/roleAssignments", {
      params: { path: { workspaceId: "ws-123" } },
      signal: undefined,
    });
  });

  it("requests workspace roles with a clamped page size", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        items: [],
        meta: {
          limit: MAX_PAGE_SIZE,
          hasMore: false,
          nextCursor: null,
          totalIncluded: false,
          totalCount: null,
          changesCursor: "0",
        },
        facets: null,
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listWorkspaceRoles({ limit: 250 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/roles", {
      params: {
        query: {
          limit: MAX_PAGE_SIZE,
          filters: JSON.stringify([{ id: "scopeType", operator: "eq", value: "workspace" }]),
        },
      },
      signal: undefined,
    });
  });

  it("requests workspace permissions scoped to the workspace with a clamped page size", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        items: [],
        meta: {
          limit: MAX_PAGE_SIZE,
          hasMore: false,
          nextCursor: null,
          totalIncluded: false,
          totalCount: null,
          changesCursor: "0",
        },
        facets: null,
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await listPermissions({ limit: 400 });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/permissions", {
      params: {
        query: {
          limit: MAX_PAGE_SIZE,
          filters: JSON.stringify([{ id: "scopeType", operator: "eq", value: "workspace" }]),
        },
      },
      signal: undefined,
    });
  });
});
