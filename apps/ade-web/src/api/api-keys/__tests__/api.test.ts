import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMyApiKey,
  createUserApiKey,
  listMyApiKeys,
  listUserApiKeys,
  revokeMyApiKey,
  revokeUserApiKey,
} from "../api";
import { client } from "@api/client";

vi.mock("@api/client", () => {
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
  page: 1,
  page_size: 25,
  has_next: false,
  has_previous: false,
  total: null,
};

describe("api key client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists my API keys with pagination flags", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: emptyPage });

    await listMyApiKeys({ page: 2, pageSize: 10, includeRevoked: true, includeTotal: true });

    expect(client.GET).toHaveBeenCalledWith("/api/v1/users/me/apiKeys", {
      params: {
        query: { page: 2, page_size: 10, include_revoked: true, include_total: true },
      },
      signal: undefined,
    });
  });

  it("creates and revokes my API keys", async () => {
    const createResponse = { id: "key-1", prefix: "abc", secret: "abc.secret" };
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: createResponse });
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });

    const created = await createMyApiKey({ name: "Automation", expires_in_days: 30 });
    expect(created).toEqual(createResponse);
    expect(client.POST).toHaveBeenCalledWith("/api/v1/users/me/apiKeys", {
      body: { name: "Automation", expires_in_days: 30 },
    });

    await revokeMyApiKey("key-1");
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/me/apiKeys/{api_key_id}", {
      params: { path: { api_key_id: "key-1" } },
    });
  });

  it("supports per-user admin routes", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: emptyPage });
    await listUserApiKeys("user-1", { includeRevoked: true });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/users/{user_id}/apiKeys", {
      params: {
        path: { user_id: "user-1" },
        query: { include_revoked: true },
      },
      signal: undefined,
    });

    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { id: "key-4", prefix: "xyz", secret: "xyz.secret" },
    });
    await createUserApiKey("user-1", { name: "Service" });
    expect(client.POST).toHaveBeenCalledWith("/api/v1/users/{user_id}/apiKeys", {
      params: { path: { user_id: "user-1" } },
      body: { name: "Service" },
    });

    await revokeUserApiKey("user-1", "key-4");
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/{user_id}/apiKeys/{api_key_id}", {
      params: { path: { user_id: "user-1", api_key_id: "key-4" } },
    });
  });
});
