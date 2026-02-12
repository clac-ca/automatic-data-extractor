import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  assignAdminUserRole,
  listAdminPermissions,
  listAdminRoles,
  removeAdminUserRole,
} from "../roles";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    DELETE: vi.fn(),
  },
}));

describe("admin roles api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists global roles with scope filter", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], meta: { limit: 50, hasMore: false, nextCursor: null, totalIncluded: false, totalCount: null, changesCursor: "0" }, facets: null },
    });

    await listAdminRoles({ limit: 10 });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/roles", {
      params: {
        query: {
          limit: 10,
          filters: JSON.stringify([{ id: "scopeType", operator: "eq", value: "global" }]),
        },
      },
      signal: undefined,
    });
  });

  it("lists global permissions and manages assignments", async () => {
    const getMock = client.GET as unknown as ReturnType<typeof vi.fn>;
    getMock
      .mockResolvedValueOnce({
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
      })
      .mockResolvedValue({
        data: {
          items: [
            {
              id: "a1",
              principal_type: "user",
              principal_id: "u1",
              role_id: "r1",
              role_slug: "global-admin",
              scope_type: "organization",
              scope_id: null,
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
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
      });
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });

    await listAdminPermissions({ scope: "global" });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/permissions", expect.any(Object));

    await assignAdminUserRole("u1", "r1");
    expect(client.POST).toHaveBeenCalledWith("/api/v1/roleAssignments", {
      body: {
        principal_type: "user",
        principal_id: "u1",
        role_id: "r1",
      },
    });

    await removeAdminUserRole("u1", "r1", { ifMatch: "*" });
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/roleAssignments/{assignmentId}", {
      params: { path: { assignmentId: expect.any(String) } },
      headers: { "If-Match": "*" },
    });
  });
});
