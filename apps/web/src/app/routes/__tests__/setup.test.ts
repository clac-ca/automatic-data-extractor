import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientActionFunctionArgs, ClientLoaderFunctionArgs } from "react-router";

import { clientAction, clientLoader } from "../setup";
import type { SessionEnvelope } from "@shared/auth/api";

const fetchSetupStatusMock = vi.fn();
const completeSetupMock = vi.fn();

vi.mock("@shared/setup/api", async () => {
  const actual = await vi.importActual<typeof import("@shared/setup/api")>(
    "@shared/setup/api",
  );
  return {
    ...actual,
    fetchSetupStatus: (options?: unknown) => fetchSetupStatusMock(options),
    completeSetup: (payload: unknown) => completeSetupMock(payload),
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

describe("setup route loader", () => {
  beforeEach(() => {
    fetchSetupStatusMock.mockReset();
  });

  it("returns loader data with sanitized redirect target", async () => {
    fetchSetupStatusMock.mockResolvedValue({ requires_setup: true, force_sso: false });

    const request = new Request("http://localhost/setup?redirectTo=/workspaces/team");
    const result = (await clientLoader({ request } as ClientLoaderFunctionArgs)) as {
      forceSso: boolean;
      redirectTo: string;
    };

    expect(result).toEqual({ forceSso: false, redirectTo: "/workspaces/team" });
  });

  it("redirects to login with preserved intent when setup already completed", async () => {
    fetchSetupStatusMock.mockResolvedValue({ requires_setup: false });

    const request = new Request("http://localhost/setup?redirectTo=/workspaces/team");
    const response = await readRedirect(clientLoader({ request } as ClientLoaderFunctionArgs));

    expect(response.headers.get("Location")).toBe("/login?redirectTo=%2Fworkspaces%2Fteam");
  });
});

describe("setup route action", () => {
  beforeEach(() => {
    completeSetupMock.mockReset();
  });

  it("redirects to the intended destination after setup completes", async () => {
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
    completeSetupMock.mockResolvedValue(session);

    const body = new URLSearchParams({
      displayName: "Casey Operator",
      email: "casey@example.com",
      password: "supersecurepw",
      confirmPassword: "supersecurepw",
      redirectTo: "/workspaces/team",
    });

    const request = new Request("http://localhost/setup", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    let caught: unknown;
    try {
      await clientAction({ request } as ClientActionFunctionArgs);
    } catch (error) {
      caught = error;
    }

    expect(completeSetupMock).toHaveBeenCalledWith({
      display_name: "Casey Operator",
      email: "casey@example.com",
      password: "supersecurepw",
    });
    expect(caught).toBeInstanceOf(Response);
    expect((caught as Response).headers.get("Location")).toBe("/workspaces/team");
  });
});
