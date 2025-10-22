import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@shared/api";
import type { ClientActionFunctionArgs, ClientLoaderFunctionArgs } from "react-router";
import { clientAction, clientLoader } from "../login";
import type { SessionEnvelope } from "@shared/auth/api";

const fetchSessionMock = vi.fn();
const fetchSetupStatusMock = vi.fn();
const createSessionMock = vi.fn();

vi.mock("@shared/auth/api", async () => {
  const actual = await vi.importActual<typeof import("@shared/auth/api")>("@shared/auth/api");
  return {
    ...actual,
    fetchSession: (options?: unknown) => fetchSessionMock(options),
    createSession: (payload: unknown, options?: unknown) => createSessionMock(payload, options),
  };
});

vi.mock("@shared/setup/api", async () => {
  const actual = await vi.importActual<typeof import("@shared/setup/api")>("@shared/setup/api");
  return {
    ...actual,
    fetchSetupStatus: (options?: unknown) => fetchSetupStatusMock(options),
  };
});

async function readRedirect(result: Promise<unknown>): Promise<Response> {
  try {
    await result;
    throw new Error("Expected redirect");
  } catch (error) {
    if (error instanceof Response) {
      return error;
    }
    throw error;
  }
}

describe("login route loader", () => {
  beforeEach(() => {
    fetchSessionMock.mockReset();
    fetchSetupStatusMock.mockReset();
    window.history.replaceState({}, "", window.location.href);
  });

  it("redirects authenticated visitors to their return destination", async () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Test User",
        permissions: [],
      },
      expires_at: null,
      refresh_expires_at: null,
      return_to: "/workspaces/123",
    };
    fetchSessionMock.mockResolvedValue(session);

    const request = new Request("http://localhost/login?redirectTo=/workspace/ignored");

    const response = await readRedirect(
      clientLoader({ request } as ClientLoaderFunctionArgs),
    );

    expect(fetchSessionMock).toHaveBeenCalled();
    expect(response.headers.get("Location")).toBe("/workspaces/123");
  });

  it("redirects to setup when initial setup is required", async () => {
    fetchSessionMock.mockResolvedValue(null);
    fetchSetupStatusMock.mockResolvedValue({ requires_setup: true });

    const request = new Request("http://localhost/login");
    const response = await readRedirect(clientLoader({ request } as ClientLoaderFunctionArgs));

    expect(fetchSetupStatusMock).toHaveBeenCalled();
    expect(response.headers.get("Location")).toBe("/setup");
  });

  it("returns sanitized redirect data when no redirects are needed", async () => {
    fetchSessionMock.mockResolvedValue(null);
    fetchSetupStatusMock.mockResolvedValue({ requires_setup: false });

    const request = new Request("http://localhost/login?redirectTo=//invalid");
    const result = (await clientLoader({ request } as ClientLoaderFunctionArgs)) as {
      redirectTo: string;
    };

    expect(result).toEqual({ redirectTo: "/workspaces" });
  });

  it("returns the sanitized redirect path from the query string", async () => {
    fetchSessionMock.mockResolvedValue(null);
    fetchSetupStatusMock.mockResolvedValue({ requires_setup: false });

    const request = new Request("http://localhost/login?redirectTo=/workspaces/alpha");
    const result = (await clientLoader({ request } as ClientLoaderFunctionArgs)) as {
      redirectTo: string;
    };

    expect(result).toEqual({ redirectTo: "/workspaces/alpha" });
  });
});

describe("login route action", () => {
  beforeEach(() => {
    createSessionMock.mockReset();
  });

  it("redirects to a sanitized destination on success", async () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Test User",
        permissions: [],
      },
      expires_at: null,
      refresh_expires_at: null,
      return_to: "/workspaces/456",
    };
    createSessionMock.mockResolvedValue(session);

    const body = new URLSearchParams({
      email: "user@example.com",
      password: "secret",
      next: "/auth/callback",
    });
    const request = new Request("http://localhost/login", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    const response = await readRedirect(clientAction({ request } as ClientActionFunctionArgs));

    expect(createSessionMock).toHaveBeenCalledWith(
      { email: "user@example.com", password: "secret" },
      expect.any(Object),
    );
    expect(response.headers.get("Location")).toBe("/workspaces/456");
  });

  it("falls back to the default destination when next is unsafe", async () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Test User",
        permissions: [],
      },
      expires_at: null,
      refresh_expires_at: null,
      return_to: null,
    };
    createSessionMock.mockResolvedValue(session);

    const body = new URLSearchParams({
      email: "user@example.com",
      password: "secret",
      next: "//evil",
    });
    const request = new Request("http://localhost/login", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    const response = await readRedirect(clientAction({ request } as ClientActionFunctionArgs));

    expect(response.headers.get("Location")).toBe("/workspaces");
  });

  it("redirects to the requested path when provided", async () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Test User",
        permissions: [],
      },
      expires_at: null,
      refresh_expires_at: null,
      return_to: null,
    };
    createSessionMock.mockResolvedValue(session);

    const body = new URLSearchParams({
      email: "user@example.com",
      password: "secret",
      redirectTo: "/workspaces/alpha",
    });
    const request = new Request("http://localhost/login", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    const response = await readRedirect(clientAction({ request } as ClientActionFunctionArgs));

    expect(response.headers.get("Location")).toBe("/workspaces/alpha");
  });

  it("returns an error message when the API rejects credentials", async () => {
    createSessionMock.mockRejectedValue(
      new ApiError("Unauthorized", 401, { detail: "Invalid credentials" }),
    );

    const body = new URLSearchParams({ email: "user@example.com", password: "wrong" });
    const request = new Request("http://localhost/login", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    const result = (await clientAction({ request } as ClientActionFunctionArgs)) as { error: string };

    expect(result).toEqual({ error: "Invalid credentials" });
  });

  it("validates form data before submitting", async () => {
    const request = new Request("http://localhost/login", {
      method: "POST",
      body: new URLSearchParams({ email: "", password: "" }),
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    const result = (await clientAction({ request } as ClientActionFunctionArgs)) as { error: string };

    expect(createSessionMock).not.toHaveBeenCalled();
    expect(result).toEqual({ error: "Enter your email address." });
  });
});
