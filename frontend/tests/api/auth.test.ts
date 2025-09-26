import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@api/client";
import { signIn } from "@api/auth";

const buildFetchMock = () => {
  const calls: Array<{ input: RequestInfo; init?: RequestInit }> = [];

  const mock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    calls.push({ input, init });
    const url = typeof input === "string" ? input : input.toString();

    if (url.endsWith("/auth/token")) {
      return new Response(JSON.stringify({ access_token: "token", token_type: "bearer" }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    if (url.endsWith("/auth/me")) {
      return new Response(
        JSON.stringify({
          user_id: "user-1",
          email: "analyst@example.com",
          role: "analyst",
          is_active: true
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
      accessToken: "token",
      user: {
        id: "user-1",
        email: "analyst@example.com",
        role: "analyst",
        isActive: true,
        displayName: "analyst"
      }
    });

    expect(calls).toHaveLength(2);

    const tokenRequest = calls[0];
    expect(String(tokenRequest.input)).toContain("/auth/token");
    const tokenHeaders = new Headers(tokenRequest.init?.headers);
    expect(tokenHeaders.get("Content-Type")).toBe("application/x-www-form-urlencoded");
    const body = tokenRequest.init?.body as URLSearchParams;
    expect(body.get("username")).toBe("analyst@example.com");
    expect(body.get("password")).toBe("secret");

    const profileRequest = calls[1];
    expect(String(profileRequest.input)).toContain("/auth/me");
    const profileHeaders = new Headers(profileRequest.init?.headers);
    expect(profileHeaders.get("Authorization")).toBe("Bearer token");
  });
});
