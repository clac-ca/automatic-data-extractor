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
  mockClient.POST.mockResolvedValue({ data: null });
  mockClient.GET.mockResolvedValue({ data: meBootstrap });
  mockApiFetch.mockResolvedValue(new Response(null, { status: 204 }));
});

afterEach(() => {
  vi.resetModules();
});

describe("auth api", () => {
  it("creates a cookie session and bootstraps profile data", async () => {
    const { createSession } = await import("../api");

    const session = await createSession({ email: "user@example.com", password: "pass" });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/cookie/login",
      expect.objectContaining({ method: "POST" }),
    );

    const loginCall = mockApiFetch.mock.calls[0]?.[1];
    const body = loginCall?.body as URLSearchParams | undefined;
    expect(body?.get("username")).toBe("user@example.com");
    expect(body?.get("password")).toBe("pass");

    expect(mockClient.GET).toHaveBeenCalledWith("/api/v1/me/bootstrap", { signal: undefined });

    expect(session.user.email).toBe("user@example.com");
  });

  it("logs out using the cookie logout route", async () => {
    const { performLogout } = await import("../api");

    await performLogout();

    expect(mockClient.POST).toHaveBeenCalledWith("/api/v1/auth/cookie/logout", {
      body: undefined,
      signal: undefined,
    });
  });
});
