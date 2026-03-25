import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { ApiError } from "@/api/errors";
import { MAX_PAGE_SIZE } from "@/api/pagination";
import {
  addWorkspaceMember,
  fetchWorkspace,
  listPermissions,
  listWorkspaceMembers,
  listWorkspaceRoles,
  removeWorkspaceMember,
  setDefaultWorkspace,
  updateWorkspaceMemberRoles,
} from "../api";

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

  it("fetches workspace detail by id", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        id: "ws-123",
        slug: "workspace-123",
        name: "Workspace 123",
        is_default: false,
        permissions: [],
        created_at: "2026-01-01T00:00:00Z",
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    const workspace = await fetchWorkspace("ws-123");

    expect(getSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}", {
      params: { path: { workspaceId: "ws-123" } },
      signal: undefined,
    });
    expect(workspace?.id).toBe("ws-123");
  });

  it("returns null when workspace detail endpoint returns 404", async () => {
    vi.spyOn(client, "GET").mockRejectedValue(new ApiError("Not found", 404));

    await expect(fetchWorkspace("missing-workspace")).resolves.toBeNull();
  });

  it("lists workspace members from the members endpoint", async () => {
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

    expect(getSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/members", {
      params: { path: { workspaceId: "ws-123" }, query: { limit: MAX_PAGE_SIZE, includeTotal: true } },
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

  it("removes workspace members through the members endpoint", async () => {
    const deleteSpy = vi
      .spyOn(client, "DELETE")
      .mockResolvedValue({ data: undefined } as Awaited<ReturnType<typeof client.DELETE>>);

    await removeWorkspaceMember("ws-123", "user-1");

    expect(deleteSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/members/{userId}", {
      params: {
        path: {
          workspaceId: "ws-123",
          userId: "user-1",
        },
      },
    });
  });

  it("adds workspace members through the members endpoint", async () => {
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue({
      data: {
        user_id: "user-1",
        role_ids: ["role-1"],
        role_slugs: ["workspace-member"],
        created_at: "2026-01-01T00:00:00Z",
        user: {
          id: "user-1",
          email: "user-1@example.com",
          display_name: "User One",
        },
        access_mode: "direct",
        is_directly_managed: true,
        sources: [],
      },
    } as unknown as Awaited<ReturnType<typeof client.POST>>);

    await addWorkspaceMember("ws-123", {
      user_id: "user-1",
      role_ids: ["role-1"],
    });

    expect(postSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/members", {
      params: { path: { workspaceId: "ws-123" } },
      body: {
        user_id: "user-1",
        role_ids: ["role-1"],
      },
    });
  });

  it("updates workspace member roles through the members endpoint", async () => {
    const putSpy = vi.spyOn(client, "PUT").mockResolvedValue({
      data: {
        user_id: "user-1",
        role_ids: ["role-1"],
        role_slugs: ["workspace-member"],
        created_at: "2026-01-01T00:00:00Z",
        user: {
          id: "user-1",
          email: "user-1@example.com",
          display_name: "User One",
        },
        access_mode: "direct",
        is_directly_managed: true,
        sources: [],
      },
    } as unknown as Awaited<ReturnType<typeof client.PUT>>);

    await updateWorkspaceMemberRoles("ws-123", "user-1", {
      role_ids: ["role-1"],
    });

    expect(putSpy).toHaveBeenCalledWith("/api/v1/workspaces/{workspaceId}/members/{userId}", {
      params: {
        path: {
          workspaceId: "ws-123",
          userId: "user-1",
        },
      },
      body: {
        role_ids: ["role-1"],
      },
    });
  });
});
