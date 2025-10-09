import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClient, get } from "../shared/api/client";

const originalFetch = globalThis.fetch;
const fetchMock = vi.fn();

function jsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "Content-Type": "application/json" }),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response;
}

describe("ApiClient", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    globalThis.fetch = fetchMock as typeof fetch;
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      // @ts-expect-error -- allow clearing fetch when unavailable.
      delete globalThis.fetch;
    }
  });

  it("prefixes API requests with the default base URL", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    await get("/setup/status");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/setup/status",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("normalizes trailing slashes on custom base URLs", async () => {
    const client = new ApiClient("https://example.com/api/");
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    await client.request("/health", { method: "GET" });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.com/api/health",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("rejects relative paths without a leading slash", async () => {
    const client = new ApiClient();

    await expect(client.request("health")).rejects.toThrow(
      /leading slash/i,
    );
  });
});
