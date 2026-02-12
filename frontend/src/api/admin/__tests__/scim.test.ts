import { beforeEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import { createScimToken, listScimTokens, revokeScimToken } from "../scim";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
  },
}));

describe("admin scim api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists scim tokens", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [],
      },
    });

    await listScimTokens();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/admin/scim/tokens", { signal: undefined });
  });

  it("creates scim token", async () => {
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        token: "scim_secret",
        item: {
          id: "3b2e5f2e-6a20-4b02-b9c2-c4fca97efec8",
          name: "Entra",
          prefix: "scim_secret",
          createdByUserId: "0d9d8f72-0873-42c6-9721-cf6f8638d970",
          createdAt: "2026-02-12T00:00:00Z",
          updatedAt: "2026-02-12T00:00:00Z",
          lastUsedAt: null,
          revokedAt: null,
        },
      },
    });

    await createScimToken({ name: "Entra" });
    expect(client.POST).toHaveBeenCalledWith("/api/v1/admin/scim/tokens", {
      body: { name: "Entra" },
    });
  });

  it("revokes scim token", async () => {
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        id: "3b2e5f2e-6a20-4b02-b9c2-c4fca97efec8",
        name: "Entra",
        prefix: "scim_secret",
        createdByUserId: "0d9d8f72-0873-42c6-9721-cf6f8638d970",
        createdAt: "2026-02-12T00:00:00Z",
        updatedAt: "2026-02-12T00:00:00Z",
        lastUsedAt: null,
        revokedAt: "2026-02-12T00:01:00Z",
      },
    });

    await revokeScimToken("3b2e5f2e-6a20-4b02-b9c2-c4fca97efec8");
    expect(client.POST).toHaveBeenCalledWith("/api/v1/admin/scim/tokens/{tokenId}/revoke", {
      params: { path: { tokenId: "3b2e5f2e-6a20-4b02-b9c2-c4fca97efec8" } },
    });
  });
});
