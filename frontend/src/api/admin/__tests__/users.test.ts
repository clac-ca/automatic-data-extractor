import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAdminUser, listAdminUsers, updateAdminUser } from "../users";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
  },
}));

describe("admin users api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists users with listing query", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], meta: { limit: 50, hasMore: false, nextCursor: null, totalIncluded: true, totalCount: 0, changesCursor: "0" }, facets: null },
    });

    await listAdminUsers({ limit: 50, search: "alice", includeTotal: true });

    expect(client.GET).toHaveBeenCalledWith("/api/v1/users", {
      params: { query: { limit: 50, q: "alice", includeTotal: true } },
      signal: undefined,
    });
  });

  it("creates and updates users", async () => {
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        user: { id: "u1" },
        passwordProvisioning: {
          mode: "explicit",
          forceChangeOnNextSignIn: false,
        },
      },
    });
    (client.PATCH as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { id: "u1" } });

    await createAdminUser({
      email: "u@example.com",
      displayName: "User",
      passwordProfile: {
        mode: "explicit",
        password: "notsecret1!Ab",
        forceChangeOnNextSignIn: false,
      },
    });
    expect(client.POST).toHaveBeenCalledWith("/api/v1/users", {
      body: {
        email: "u@example.com",
        displayName: "User",
        passwordProfile: {
          mode: "explicit",
          password: "notsecret1!Ab",
          forceChangeOnNextSignIn: false,
        },
      },
    });

    await updateAdminUser("u1", { display_name: "Updated" });
    expect(client.PATCH).toHaveBeenCalledWith("/api/v1/users/{userId}", {
      params: { path: { userId: "u1" } },
      body: { display_name: "Updated" },
    });
  });
});
