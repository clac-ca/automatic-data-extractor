import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import {
  chunkUserBatchRequests,
  executeUserBatch,
  executeUserBatchChunked,
  fetchUsers,
} from "../api";

describe("users api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches users with normalized list query params", async () => {
    const getSpy = vi.spyOn(client, "GET").mockResolvedValue({
      data: {
        items: [],
        meta: {
          limit: 50,
          hasMore: false,
          nextCursor: null,
          totalIncluded: false,
          totalCount: null,
          changesCursor: "0",
        },
        facets: null,
      },
    } as unknown as Awaited<ReturnType<typeof client.GET>>);

    await fetchUsers({ limit: 25, search: "  test-user  " });

    expect(getSpy).toHaveBeenCalledWith("/api/v1/users", {
      params: {
        query: {
          limit: 25,
          q: "test-user",
        },
      },
      signal: undefined,
    });
  });

  it("posts a Graph-style batch payload", async () => {
    const postSpy = vi.spyOn(client, "POST").mockResolvedValue({
      data: {
        responses: [{ id: "one", status: 200, body: { id: "user-1" } }],
      },
    } as unknown as Awaited<ReturnType<typeof client.POST>>);

    await executeUserBatch({
      requests: [
        {
          id: "one",
          method: "PATCH",
          url: "/users/00000000-0000-0000-0000-000000000001",
          body: { department: "Finance" },
          dependsOn: [],
        },
      ],
    });

    expect(postSpy).toHaveBeenCalledWith("/api/v1/$batch", {
      body: {
        requests: [
          {
            id: "one",
            method: "PATCH",
            url: "/users/00000000-0000-0000-0000-000000000001",
            body: { department: "Finance" },
            dependsOn: [],
          },
        ],
      },
    });
  });

  it("chunks user batch requests at the requested size", () => {
    const requests = Array.from({ length: 5 }, (_, index) => ({
      id: `req-${index}`,
      method: "PATCH",
      url: `/users/00000000-0000-0000-0000-00000000000${index}`,
      body: { department: `Dept ${index}` },
      dependsOn: [],
    }));

    const chunks = chunkUserBatchRequests(requests, 2);
    expect(chunks).toHaveLength(3);
    expect(chunks[0]).toHaveLength(2);
    expect(chunks[1]).toHaveLength(2);
    expect(chunks[2]).toHaveLength(1);
  });

  it("executes chunked user batches and merges responses", async () => {
    const postSpy = vi.spyOn(client, "POST");
    postSpy
      .mockResolvedValueOnce({
        data: {
          responses: [{ id: "req-1", status: 200, body: { ok: true } }],
        },
      } as unknown as Awaited<ReturnType<typeof client.POST>>)
      .mockResolvedValueOnce({
        data: {
          responses: [{ id: "req-2", status: 200, body: { ok: true } }],
        },
      } as unknown as Awaited<ReturnType<typeof client.POST>>);

    const merged = await executeUserBatchChunked(
      [
        {
          id: "req-1",
          method: "POST",
          url: "/users",
          body: {
            email: "one@example.com",
            passwordProfile: {
              mode: "explicit",
              password: "notsecret1!Ab",
              forceChangeOnNextSignIn: false,
            },
          },
          dependsOn: [],
        },
        {
          id: "req-2",
          method: "POST",
          url: "/users",
          body: {
            email: "two@example.com",
            passwordProfile: {
              mode: "explicit",
              password: "notsecret1!Ab",
              forceChangeOnNextSignIn: false,
            },
          },
          dependsOn: [],
        },
      ],
      1,
    );

    expect(postSpy).toHaveBeenCalledTimes(2);
    expect(merged.responses).toHaveLength(2);
    expect(merged.responses.map((item) => item.id)).toEqual(["req-1", "req-2"]);
  });

  it("rejects chunking when dependsOn crosses chunk boundaries", async () => {
    const postSpy = vi.spyOn(client, "POST");

    await expect(
      executeUserBatchChunked(
        [
          {
            id: "req-1",
            method: "POST",
            url: "/users",
            body: {
              email: "one@example.com",
              passwordProfile: {
                mode: "explicit",
                password: "notsecret1!Ab",
                forceChangeOnNextSignIn: false,
              },
            },
            dependsOn: [],
          },
          {
            id: "req-2",
            method: "PATCH",
            url: "/users/00000000-0000-0000-0000-000000000002",
            body: {
              department: "Finance",
            },
            dependsOn: ["req-1"],
          },
        ],
        1,
      ),
    ).rejects.toThrow(/dependsOn relationships across chunks/i);

    expect(postSpy).not.toHaveBeenCalled();
  });
});
