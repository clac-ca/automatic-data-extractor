import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError } from "@api/client";

function createOkResponse(data: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init
  });
}

describe("ApiClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(createOkResponse({ success: true }));
  });

  it("adds authorization header when access token is available", async () => {
    const client = new ApiClient({
      getAccessToken: () => "token-123",
      fetchImplementation: fetchMock
    });

    await client.get("/sample");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [RequestInfo, RequestInit];
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-123");
  });

  it("serialises query parameters", async () => {
    const client = new ApiClient({ fetchImplementation: fetchMock });

    await client.get("/search", { query: { page: 2, q: "invoice" } });

    const [requestUrl] = fetchMock.mock.calls[0] as [RequestInfo];
    expect(String(requestUrl)).toContain("page=2");
    expect(String(requestUrl)).toContain("q=invoice");
  });

  it("stringifies JSON payloads", async () => {
    const client = new ApiClient({ fetchImplementation: fetchMock });

    await client.post("/documents", { json: { name: "report" } });

    const [, init] = fetchMock.mock.calls[0] as [RequestInfo, RequestInit];
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(init?.body).toBe(JSON.stringify({ name: "report" }));
  });

  it("throws ApiError when response is not ok", async () => {
    const errorResponse = new Response(JSON.stringify({ message: "Failure" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
    fetchMock.mockResolvedValue(errorResponse);
    const client = new ApiClient({ fetchImplementation: fetchMock });

    await expect(client.get("/broken")).rejects.toThrow(ApiError);

    const error = await client.get("/broken").catch((err) => err as ApiError);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(error.detail).toEqual({ message: "Failure" });
  });
});
