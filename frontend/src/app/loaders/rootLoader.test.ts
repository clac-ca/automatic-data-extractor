import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";

import { rootLoader } from "./rootLoader";
import { appQueryClient } from "../providers";
import { sessionKeys } from "../../features/auth/hooks/sessionKeys";
import { setupKeys } from "../../features/setup/hooks/useSetupStatusQuery";
import { fetchSession } from "../../features/auth/api";
import { fetchSetupStatus } from "../../features/setup/api";

vi.mock("../../features/auth/api", () => ({
  fetchSession: vi.fn(),
}));

vi.mock("../../features/setup/api", () => ({
  fetchSetupStatus: vi.fn(),
}));

describe("rootLoader", () => {
  beforeEach(() => {
    appQueryClient.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    appQueryClient.clear();
  });

  it("prefetches session and setup status", async () => {
    const session = {
      user: {
        user_id: "user-123",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
      },
      expires_at: "2025-01-01T00:00:00Z",
      refresh_expires_at: "2025-01-02T00:00:00Z",
    };
    const setupStatus = { requires_setup: false, completed_at: "2024-01-01T00:00:00Z", force_sso: false };

    vi.mocked(fetchSession).mockResolvedValue(session);
    vi.mocked(fetchSetupStatus).mockResolvedValue(setupStatus);

    const result = await rootLoader();

    expect(result).toEqual({ session, setupStatus, setupError: null });
    expect(appQueryClient.getQueryData(sessionKeys.detail())).toEqual(session);
    expect(appQueryClient.getQueryData(setupKeys.status())).toEqual(setupStatus);
  });

  it("returns a setup error when status prefetch fails", async () => {
    const error = new Error("boom");
    const session = {
      user: {
        user_id: "user-123",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
      },
      expires_at: "2025-01-01T00:00:00Z",
      refresh_expires_at: "2025-01-02T00:00:00Z",
    };

    vi.mocked(fetchSession).mockResolvedValue(session);
    vi.mocked(fetchSetupStatus).mockRejectedValue(error);

    const result = await rootLoader();

    expect(result).toEqual({ session, setupStatus: null, setupError: error });
    expect(appQueryClient.getQueryData(sessionKeys.detail())).toEqual(session);
    expect(appQueryClient.getQueryState(setupKeys.status())?.status).toBe("error");
  });

  it("propagates session failures", async () => {
    const error = new Error("session failed");

    vi.mocked(fetchSession).mockRejectedValue(error);
    vi.mocked(fetchSetupStatus).mockResolvedValue({
      requires_setup: true,
      completed_at: null,
      force_sso: false,
    });

    await expect(rootLoader()).rejects.toBe(error);
  });
});
