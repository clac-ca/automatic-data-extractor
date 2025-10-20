import { describe, it, beforeEach, afterEach, vi, expect } from "vitest";
import { render } from "@test/test-utils";
import type { SessionEnvelope } from "@schema/auth";
import { SessionProvider } from "../SessionContext";
import { refreshSession } from "../../api";

vi.mock("../../api", () => ({
  refreshSession: vi.fn(),
}));

describe("SessionProvider", () => {
  const mockedRefreshSession = vi.mocked(refreshSession);

  beforeEach(() => {
    vi.useFakeTimers();
    mockedRefreshSession.mockReset();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("refreshes the session shortly before expiry", async () => {
    const refetch = vi.fn().mockResolvedValue(undefined);
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
      },
      expires_at: new Date(Date.now() + 70_000).toISOString(),
      refresh_expires_at: new Date(Date.now() + 600_000).toISOString(),
      return_to: null,
    };

    mockedRefreshSession.mockResolvedValueOnce({
      ...session,
      expires_at: new Date(Date.now() + 170_000).toISOString(),
    });

    render(
      <SessionProvider session={session} refetch={refetch}>
        <div>Child</div>
      </SessionProvider>,
    );

    await vi.advanceTimersByTimeAsync(15_000);

    expect(mockedRefreshSession).toHaveBeenCalledTimes(1);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("falls back to refetch when the refresh request fails", async () => {
    const refetch = vi.fn().mockResolvedValue(undefined);
    const session: SessionEnvelope = {
      user: {
        user_id: "user-2",
        email: "other@example.com",
        is_active: true,
        is_service_account: false,
      },
      expires_at: new Date(Date.now() + 70_000).toISOString(),
      refresh_expires_at: new Date(Date.now() + 600_000).toISOString(),
      return_to: null,
    };

    mockedRefreshSession.mockRejectedValueOnce(new Error("boom"));

    render(
      <SessionProvider session={session} refetch={refetch}>
        <div>Child</div>
      </SessionProvider>,
    );

    await vi.advanceTimersByTimeAsync(15_000);

    expect(mockedRefreshSession).toHaveBeenCalledTimes(1);
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
