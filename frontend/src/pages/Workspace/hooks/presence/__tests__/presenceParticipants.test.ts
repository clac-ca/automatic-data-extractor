import { describe, expect, it } from "vitest";

import type { PresenceParticipant } from "@/types/presence";

import {
  dedupePresenceParticipants,
  filterParticipantsByPage,
  mapPresenceByDocument,
} from "../presenceParticipants";

function participant(overrides: Partial<PresenceParticipant>): PresenceParticipant {
  return {
    client_id: "client-default",
    user_id: "user-default",
    display_name: "User",
    email: "user@example.com",
    status: "idle",
    presence: null,
    selection: null,
    editing: null,
    ...overrides,
  };
}

describe("presenceParticipants", () => {
  it("dedupes by user and keeps higher-ranked participant snapshots", () => {
    const items = [
      participant({
        client_id: "client-a-1",
        user_id: "user-a",
        display_name: "Alpha",
        status: "idle",
        selection: null,
      }),
      participant({
        client_id: "client-a-2",
        user_id: "user-a",
        display_name: "Alpha",
        status: "active",
        selection: { documentId: "doc_1" },
      }),
      participant({
        client_id: "client-b-1",
        user_id: "user-b",
        display_name: "Beta",
        status: "active",
      }),
    ];

    const deduped = dedupePresenceParticipants(items);
    expect(deduped.map((item) => item.user_id)).toEqual(["user-a", "user-b"]);
    expect(deduped[0]?.client_id).toBe("client-a-2");
  });

  it("filters participants by page", () => {
    const items = [
      participant({ client_id: "client-doc", presence: { page: "documents" } }),
      participant({ client_id: "client-runs", presence: { page: "runs" } }),
      participant({ client_id: "client-none", presence: null }),
    ];

    const filtered = filterParticipantsByPage(items, "documents");
    expect(filtered.map((item) => item.client_id)).toEqual(["client-doc"]);
  });

  it("maps participants by document and keeps current user/client metadata", () => {
    const items = [
      participant({
        client_id: "client-self",
        user_id: "self",
        display_name: "Self",
        presence: { page: "documents" },
        selection: { documentId: "doc_1" },
      }),
      participant({
        client_id: "client-peer-1",
        user_id: "peer",
        display_name: "Peer",
        status: "active",
        presence: { page: "documents" },
        selection: { documentId: "doc_1" },
      }),
      participant({
        client_id: "client-peer-2",
        user_id: "peer",
        display_name: "Peer",
        status: "idle",
        presence: { page: "documents" },
        selection: { documentId: "doc_1" },
      }),
      participant({
        client_id: "client-other",
        user_id: "other",
        display_name: "Other",
        status: "active",
        presence: { page: "documents" },
        selection: { documentId: "doc_2" },
      }),
    ];

    const mapped = mapPresenceByDocument(items, {
      currentUserId: "self",
      currentClientId: "client-self",
    });
    const docOne = mapped.get("doc_1") ?? [];
    expect(docOne).toHaveLength(2);
    expect(docOne.find((entry) => entry.participant.user_id === "self")?.isCurrentUser).toBe(true);
    expect(docOne.find((entry) => entry.participant.user_id === "self")?.isCurrentClient).toBe(true);
    expect(docOne.find((entry) => entry.participant.user_id === "peer")?.participant.client_id).toBe(
      "client-peer-1",
    );
    expect(mapped.get("doc_2")?.map((entry) => entry.participant.user_id)).toEqual(["other"]);
  });

  it("collapses same-user multi-tab presence into one row entry with tab count", () => {
    const items = [
      participant({
        client_id: "client-self-a",
        user_id: "self",
        status: "active",
        presence: { page: "documents" },
        selection: { documentId: "doc_1" },
      }),
      participant({
        client_id: "client-self-b",
        user_id: "self",
        status: "idle",
        presence: { page: "documents" },
        selection: { documentId: "doc_1" },
      }),
    ];

    const mapped = mapPresenceByDocument(items, {
      currentUserId: "self",
      currentClientId: "client-self-a",
    });
    const docOne = mapped.get("doc_1") ?? [];
    expect(docOne).toHaveLength(1);
    expect(docOne[0]?.tabCountForUser).toBe(2);
    expect(docOne[0]?.isCurrentUser).toBe(true);
    expect(docOne[0]?.participant.client_id).toBe("client-self-a");
  });
});
