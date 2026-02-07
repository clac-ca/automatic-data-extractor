import { beforeEach, describe, expect, it, vi } from "vitest";

import { listTenantApiKeys, revokeAdminUserApiKey } from "../api-keys";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    DELETE: vi.fn(),
  },
}));

describe("admin api keys api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists tenant keys and supports user filter", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], meta: { limit: 50, hasMore: false, nextCursor: null, totalIncluded: true, totalCount: 0, changesCursor: "0" }, facets: null },
    });

    await listTenantApiKeys({ userId: "u1", includeRevoked: true, limit: 25 });

    expect(client.GET).toHaveBeenCalledWith("/api/v1/apikeys", {
      params: { query: { limit: 25, userId: "u1" } },
      signal: undefined,
    });
  });

  it("revokes a user api key", async () => {
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });

    await revokeAdminUserApiKey("u1", "k1", { ifMatch: "*" });
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/{userId}/apikeys/{apiKeyId}", {
      params: {
        path: { userId: "u1", apiKeyId: "k1" },
        header: { "If-Match": "*" },
      },
    });
  });
});
