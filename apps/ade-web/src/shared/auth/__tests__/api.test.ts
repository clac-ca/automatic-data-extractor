import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockClient = {
  POST: vi.fn(),
  DELETE: vi.fn(),
  GET: vi.fn(),
};

vi.mock("@shared/api/client", () => ({
  client: mockClient,
}));

function createMockStorage() {
  const store = new Map<string, string>();
  return {
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
  };
}

const meBootstrap = {
  user: {
    id: "user-1",
    email: "user@example.com",
    display_name: "User",
    is_service_account: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  workspaces: {
    items: [],
    page: 1,
    page_size: 50,
    total: 0,
    has_next: false,
    has_previous: false,
  },
  global_roles: [],
  global_permissions: [],
};

async function loadApi(initialStorage?: Record<string, unknown>) {
  vi.resetModules();
  const storage = createMockStorage();
  if (initialStorage) {
    storage.setItem("ade.auth.tokens", JSON.stringify(initialStorage));
  }
  (globalThis as unknown as { window: unknown }).window = { localStorage: storage };
  (globalThis as unknown as { localStorage: unknown }).localStorage = storage;

  mockClient.POST.mockReset();
  mockClient.DELETE.mockReset();
  mockClient.GET.mockReset();

  mockClient.POST.mockResolvedValue({ data: null });
  mockClient.DELETE.mockResolvedValue({ data: null });
  mockClient.GET.mockResolvedValue({ data: meBootstrap });

  return {
    storage,
    api: await import("../api"),
  };
}

beforeEach(() => {
  mockClient.POST.mockResolvedValue({ data: null });
  mockClient.DELETE.mockResolvedValue({ data: null });
  mockClient.GET.mockResolvedValue({ data: meBootstrap });
});

afterEach(() => {
  vi.resetModules();
  // @ts-expect-error reset test globals
  delete globalThis.window;
  // @ts-expect-error reset test globals
  delete globalThis.localStorage;
});

describe("auth api", () => {
  it("refreshes using the cookie flow without persisting a refresh token", async () => {
    const { api, storage } = await loadApi();

    const issued = {
      access_token: "new-access",
      refresh_token: "new-refresh",
      token_type: "bearer",
      expires_in: 120,
      refresh_expires_in: 300,
    };

    mockClient.POST.mockResolvedValueOnce({ data: issued });

    await api.refreshSession();

    expect(mockClient.POST).toHaveBeenCalledWith("/api/v1/auth/session/refresh", {
      body: undefined,
      signal: undefined,
    });

    const stored = JSON.parse(storage.getItem("ade.auth.tokens") ?? "{}") as Record<string, unknown>;
    expect(stored).toMatchObject({
      access_token: "new-access",
      token_type: "bearer",
    });
    expect(stored.refresh_token).toBeUndefined();
  });

  it("logs out without a refresh token payload and clears stored tokens", async () => {
    const initial = {
      access_token: "existing-access",
      token_type: "bearer",
      expires_at: Date.now() + 60_000,
      refresh_expires_at: Date.now() + 300_000,
    };

    const { api, storage } = await loadApi(initial);

    await api.performLogout();

    expect(mockClient.DELETE).toHaveBeenCalledWith("/api/v1/auth/session", {
      body: undefined,
      signal: undefined,
    });
    expect(storage.getItem("ade.auth.tokens")).toBeNull();
  });
});
