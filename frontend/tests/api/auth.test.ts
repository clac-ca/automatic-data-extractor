import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@api/client";
import { signIn, signOut } from "@api/auth";

const buildFetchMock = () => {
  const calls: Array<{ input: RequestInfo; init?: RequestInit }> = [];

  const mock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    calls.push({ input, init });
    const url = typeof input === "string" ? input : input.toString();

    if (url.endsWith("/auth/login")) {
      return new Response(
        JSON.stringify({
          user: {
            user_id: "user-1",
            email: "analyst@example.com",
            role: "analyst",
            is_active: true
          },
          expires_at: "2024-01-01T00:00:00Z",
          refresh_expires_at: "2024-01-15T00:00:00Z"
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      );
    }

    return new Response(null, { status: 404 });
  });

  return { calls, mock };
};

describe("signIn", () => {
  it("submits credentials to the backend and returns session details", async () => {
    const { calls, mock } = buildFetchMock();
    const client = new ApiClient({ fetchImplementation: mock });

    const session = await signIn(client, {
      email: "analyst@example.com",
      password: "secret"
    });

    expect(session).toEqual({
      user: {
        id: "user-1",
        email: "analyst@example.com",
        role: "analyst",
        isActive: true,
        displayName: "analyst"
      },
      expiresAt: "2024-01-01T00:00:00Z",
      refreshExpiresAt: "2024-01-15T00:00:00Z"
    });

    expect(calls).toHaveLength(1);

    const request = calls[0];
    expect(String(request.input)).toContain("/auth/login");
    expect(request.init?.method).toBe("POST");
    const headers = new Headers(request.init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(request.init?.body).toBe(JSON.stringify({
      email: "analyst@example.com",
      password: "secret"
    }));
  });

  it("invokes the logout endpoint", async () => {
    const { calls, mock } = buildFetchMock();
    mock.mockImplementationOnce(async () =>
      new Response(null, { status: 204, headers: { "Content-Type": "application/json" } })
    );

    const client = new ApiClient({ fetchImplementation: mock });
    await signOut(client);

    expect(calls).toHaveLength(1);
    expect(String(calls[0].input)).toContain("/auth/logout");
    expect(calls[0].init?.method).toBe("POST");
  });
});
