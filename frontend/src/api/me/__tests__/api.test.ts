import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchMyProfile, updateMyProfile } from "../api";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    PATCH: vi.fn(),
  },
}));

const sampleProfile = {
  id: "user-1",
  email: "user@example.com",
  display_name: "User",
  is_service_account: false,
  preferred_workspace_id: null,
  roles: [],
  permissions: [],
  created_at: "2026-01-01T00:00:00Z",
};

describe("me api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches the current profile", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: sampleProfile });

    const profile = await fetchMyProfile();

    expect(client.GET).toHaveBeenCalledWith("/api/v1/me", { signal: undefined });
    expect(profile).toEqual(sampleProfile);
  });

  it("patches profile display name", async () => {
    const updated = { ...sampleProfile, display_name: "Data Operations" };
    (client.PATCH as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: updated });

    const profile = await updateMyProfile({ display_name: "Data Operations" });

    expect(client.PATCH).toHaveBeenCalledWith("/api/v1/me", {
      body: { display_name: "Data Operations" },
    });
    expect(profile).toEqual(updated);
  });
});
