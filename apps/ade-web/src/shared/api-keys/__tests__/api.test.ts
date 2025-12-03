import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createApiKey,
  createMyApiKey,
  createUserApiKey,
  getApiKey,
  listApiKeys,
  listMyApiKeys,
  listUserApiKeys,
  revokeApiKey,
  revokeMyApiKey,
  revokeUserApiKey,
} from "../api";
import { client } from "@shared/api/client";

vi.mock("@shared/api/client", () => {
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

    expect(client.GET).toHaveBeenCalledWith("/api/v1/me/api-keys", {
      params: {
        query: { page: 2, page_size: 10, include_revoked: true, include_total: true },
      },
      signal: undefined,
    });
  });

  it("creates and revokes my API keys", async () => {
    const createResponse = { id: "key-1", token_prefix: "abc", secret: "abc.secret" };
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: createResponse });
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });

    const created = await createMyApiKey({ scope_type: "global" });
    expect(created).toEqual(createResponse);
    expect(client.POST).toHaveBeenCalledWith("/api/v1/me/api-keys", { body: { scope_type: "global" } });

    await revokeMyApiKey("key-1");
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/me/api-keys/{api_key_id}", {
      params: { path: { api_key_id: "key-1" } },
    });
  });

  it("supports admin list/get/create/revoke paths", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: emptyPage });
    await listApiKeys({ page: 1, ownerUserId: "owner-1", includeRevoked: true });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/api-keys", {
      params: {
        query: { page: 1, include_revoked: true, owner_user_id: "owner-1" },
      },
      signal: undefined,
    });

    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: { id: "key-2" } });
    await getApiKey("key-2");
    expect(client.GET).toHaveBeenCalledWith("/api/v1/api-keys/{api_key_id}", {
      params: { path: { api_key_id: "key-2" } },
    });

    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { id: "key-3", token_prefix: "zzz", secret: "zzz.secret" },
    });
    await createApiKey({ email: "user@example.com", scope_type: "global" });
    expect(client.POST).toHaveBeenCalledWith("/api/v1/api-keys", {
      body: { email: "user@example.com", scope_type: "global" },
    });

    await revokeApiKey("key-3");
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/api-keys/{api_key_id}", {
      params: { path: { api_key_id: "key-3" } },
    });
  });

  it("supports per-user admin routes", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: emptyPage });
    await listUserApiKeys("user-1", { includeRevoked: true });
    expect(client.GET).toHaveBeenCalledWith("/api/v1/users/{user_id}/api-keys", {
      params: {
        path: { user_id: "user-1" },
        query: { include_revoked: true },
      },
      signal: undefined,
    });

    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { id: "key-4", token_prefix: "xyz", secret: "xyz.secret" },
    });
    await createUserApiKey("user-1", { scope_type: "global" });
    expect(client.POST).toHaveBeenCalledWith("/api/v1/users/{user_id}/api-keys", {
      params: { path: { user_id: "user-1" } },
      body: { scope_type: "global" },
    });

    await revokeUserApiKey("user-1", "key-4");
    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/users/{user_id}/api-keys/{api_key_id}", {
      params: { path: { user_id: "user-1", api_key_id: "key-4" } },
    });
  });
});
