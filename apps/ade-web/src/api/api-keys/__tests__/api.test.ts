import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMyApiKey,
  createUserApiKey,
  listMyApiKeys,
  listUserApiKeys,
  revokeMyApiKey,
  revokeUserApiKey,
} from "../api";
import { client } from "@/api/client";

vi.mock("@/api/client", () => {
  return {
    client: {
      GET: vi.fn(),
      POST: vi.fn(),
      DELETE: vi.fn(),
    },
  };
});

const emptyPage = {
  items: [],
  meta: {
    limit: 25,
    hasMore: false,
    nextCursor: null,
    totalIncluded: false,
    totalCount: null,
    changesCursor: "0",
  },
  facets: null,
};

describe("api key client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists my API keys with pagination flags", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: emptyPage });

    await listMyApiKeys({ limit: 10, cursor: "cursor-1", includeRevoked: true });

    expect(client.GET).toHaveBeenCalledWith("/api/v1/users/me/apikeys", {
      params: {
        query: { limit: 10, cursor: "cursor-1" },
      },
      signal: undefined,
    });
  });

  it("creates and revokes my API keys", async () => {
    const createResponse = { id: "key-1", prefix: "abc", secret: "abc.secret" };
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: createResponse });
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });

    const created = await createMyApiKey({ name: "Automation", expires_in_days: 30 }, "idem-key-1");
    expect(created).toEqual(createResponse);
    expect(client.POST).toHaveBeenCalledWith("/api/v1/users/me/apikeys", {
      body: { name: "Automation", expires_in_days: 30 },
      headers: { "Idempotency-Key": "idem-key-1" },
    });

    await revokeMyApiKey("key-1", { ifMatch: 'W/"key-1:etag"' });
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/me/apikeys/{apiKeyId}", {
      params: { path: { apiKeyId: "key-1" } },
      headers: { "If-Match": 'W/"key-1:etag"' },
    });
  });

  it("supports per-user admin routes", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: emptyPage });
    await listUserApiKeys("user-1", { includeRevoked: true });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/users/{userId}/apikeys", {
      params: {
        path: { userId: "user-1" },
        query: {},
      },
      signal: undefined,
    });

    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { id: "key-4", prefix: "xyz", secret: "xyz.secret" },
    });
    await createUserApiKey("user-1", { name: "Service" }, "idem-key-2");
    expect(client.POST).toHaveBeenCalledWith("/api/v1/users/{userId}/apikeys", {
      params: { path: { userId: "user-1" } },
      body: { name: "Service" },
      headers: { "Idempotency-Key": "idem-key-2" },
    });

    await revokeUserApiKey("user-1", "key-4", { ifMatch: 'W/"key-4:etag"' });
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/{userId}/apikeys/{apiKeyId}", {
      params: { path: { userId: "user-1", apiKeyId: "key-4" } },
      headers: { "If-Match": 'W/"key-4:etag"' },
    });
  });
});
