import { beforeEach, describe, expect, it, vi } from "vitest";

import { listSsoProviders, readSafeModeStatus, updateSafeModeStatus } from "../sso";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    PUT: vi.fn(),
  },
}));

describe("admin sso api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists SSO providers", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [] } });
    await listSsoProviders();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/admin/sso/providers", { signal: undefined });
  });

  it("updates and rereads safe mode", async () => {
    (client.PUT as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { enabled: true, detail: "Maint" } });

    const updated = await updateSafeModeStatus({ enabled: true, detail: "Maint" });
    expect(client.PUT).toHaveBeenCalledWith("/api/v1/system/safemode", {
      body: { enabled: true, detail: "Maint" },
    });
    expect(updated).toEqual({ enabled: true, detail: "Maint" });

    await readSafeModeStatus();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/system/safemode", { signal: undefined });
  });
});
