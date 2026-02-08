import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockClient = {
  POST: vi.fn(),
  GET: vi.fn(),
};

const mockApiFetch = vi.fn();

vi.mock("@/api/client", () => ({
  client: mockClient,
  apiFetch: mockApiFetch,
}));

const meBootstrap = {
  user: {
    id: "user-1",
    email: "user@example.com",
    display_name: "User",
    is_service_account: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  workspaces: [],
  roles: [],
  permissions: [],
};

beforeEach(() => {
  mockClient.POST.mockReset();
  mockClient.GET.mockReset();
  mockApiFetch.mockReset();
  mockClient.POST.mockResolvedValue({ data: null });
  mockClient.GET.mockResolvedValue({ data: meBootstrap });
  mockApiFetch.mockResolvedValue(new Response(JSON.stringify({ ok: true, mfa_required: false }), { status: 200 }));
});

afterEach(() => {
  vi.resetModules();
});

describe("auth api", () => {
  it("creates a cookie session and bootstraps profile data", async () => {
    const { createSession } = await import("../api");

    const result = await createSession({ email: "user@example.com", password: "pass" });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "user@example.com", password: "pass" }),
      }),
    );

    expect(mockClient.GET).toHaveBeenCalledWith("/api/v1/me/bootstrap", { signal: undefined });
    expect(result.kind).toBe("session");
    if (result.kind === "session") {
      expect(result.session.user.email).toBe("user@example.com");
    }
  });

  it("returns challenge token when MFA is required", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ok: true, mfa_required: true, challengeToken: "challenge-123" }),
        { status: 200 },
      ),
    );

    const { createSession } = await import("../api");
    const result = await createSession({ email: "user@example.com", password: "pass" });

    expect(result).toEqual({
      kind: "mfa_required",
      challengeToken: "challenge-123",
    });
    expect(mockClient.GET).not.toHaveBeenCalled();
  });

  it("logs out using the auth logout route", async () => {
    const { performLogout } = await import("../api");

    await performLogout();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({ method: "POST", signal: undefined }),
    );
  });
});
