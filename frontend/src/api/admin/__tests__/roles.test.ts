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
    PUT: vi.fn(),
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
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], meta: { limit: 50, hasMore: false, nextCursor: null, totalIncluded: false, totalCount: null, changesCursor: "0" }, facets: null },
    });
    (client.PUT as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { user_id: "u1", roles: [] } });
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });

    await listAdminPermissions({ scope: "global" });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/permissions", expect.any(Object));

    await assignAdminUserRole("u1", "r1");
    expect(client.PUT).toHaveBeenCalledWith("/api/v1/users/{userId}/roles/{roleId}", {
      params: { path: { userId: "u1", roleId: "r1" } },
    });

    await removeAdminUserRole("u1", "r1", { ifMatch: "*" });
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/{userId}/roles/{roleId}", {
      params: { path: { userId: "u1", roleId: "r1" } },
      headers: { "If-Match": "*" },
    });
  });
});
