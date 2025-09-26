/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />

import { renderHook, waitFor } from "@testing-library/react";

import { useWorkspaceContextQuery, useWorkspacesQuery } from "../src/app/workspaces/hooks";
import { ApiError } from "../src/api/errors";
import { createTestQueryClient, createTestWrapper } from "./utils";

vi.mock("../src/app/auth/AuthContext", () => {
  const React = require("react");
  const stubValue = {
    status: "authenticated" as const,
    token: "test-token",
    email: "tester@example.com",
    error: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    clearError: vi.fn(),
  };

  return {
    AuthProvider: ({ children }: { children: React.ReactNode }) => (
      <React.Fragment>{children}</React.Fragment>
    ),
    useAuth: () => stubValue,
  };
});

describe("workspace queries", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns workspaces when the API call succeeds", async () => {
    const payload = [
      {
        workspace_id: "alpha",
        name: "Alpha",
        slug: "alpha",
        role: "OWNER",
        permissions: ["workspace:read"],
        is_default: true,
      },
    ];

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));

    const { result } = renderHook(() => useWorkspacesQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/workspaces"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
    expect(result.current.data).toEqual(payload);
  });

  it("handles empty workspace lists", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    const { result } = renderHook(() => useWorkspacesQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it("surfaces errors for unauthorized requests", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
        statusText: "Unauthorized",
      }),
    );

    const queryClient = createTestQueryClient();

    const { result } = renderHook(() => useWorkspacesQuery(), {
      wrapper: createTestWrapper({ queryClient }),
    });

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(queryClient.getQueryState(["workspaces"])?.error).toBeInstanceOf(ApiError);
  });

  it("returns workspace context when provided an identifier", async () => {
    const payload = {
      workspace: {
        workspace_id: "alpha",
        name: "Alpha",
        slug: "alpha",
        role: "OWNER",
        permissions: ["workspace:read"],
        is_default: true,
      },
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    const { result } = renderHook(() => useWorkspaceContextQuery("alpha"), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(payload);
  });
});
