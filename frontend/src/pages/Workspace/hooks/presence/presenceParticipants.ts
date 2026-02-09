import type { PresenceParticipant } from "@/types/presence";

export type DocumentPresenceEntry = {
  participant: PresenceParticipant;
  isCurrentUser: boolean;
  isCurrentClient: boolean;
  tabCountForUser: number;
};

type MapPresenceByDocumentOptions = {
  currentUserId?: string | null;
  currentClientId?: string | null;
};

export function getPresenceParticipantLabel(participant: PresenceParticipant) {
  return participant.display_name || participant.email || "Workspace member";
}

export function getPresencePage(participant: PresenceParticipant) {
  const presence = participant.presence;
  if (!presence || typeof presence !== "object") return null;
  const page = presence["page"];
  return typeof page === "string" ? page : null;
}

export function getSelectedDocumentId(participant: PresenceParticipant) {
  const selection = participant.selection;
  if (!selection || typeof selection !== "object") return null;
  const documentId = selection["documentId"];
  return typeof documentId === "string" ? documentId : null;
}

export function rankPresenceParticipant(participant: PresenceParticipant) {
  let score = 0;
  if (participant.status === "active") score += 2;
  if (getSelectedDocumentId(participant)) score += 3;
  if (participant.editing) score += 1;
  return score;
}

function getParticipantStableKey(participant: PresenceParticipant) {
  return participant.user_id || participant.client_id;
}

function compareParticipants(a: PresenceParticipant, b: PresenceParticipant) {
  const scoreDelta = rankPresenceParticipant(b) - rankPresenceParticipant(a);
  if (scoreDelta !== 0) return scoreDelta;

  const aStatusRank = a.status === "active" ? 0 : 1;
  const bStatusRank = b.status === "active" ? 0 : 1;
  if (aStatusRank !== bStatusRank) return aStatusRank - bStatusRank;

  const labelDelta = getPresenceParticipantLabel(a)
    .toLowerCase()
    .localeCompare(getPresenceParticipantLabel(b).toLowerCase());
  if (labelDelta !== 0) return labelDelta;

  return a.client_id.localeCompare(b.client_id);
}

export function sortPresenceParticipants(participants: PresenceParticipant[]) {
  return [...participants].sort(compareParticipants);
}

export function dedupePresenceParticipants(participants: PresenceParticipant[]) {
  const byUser = new Map<string, PresenceParticipant>();
  for (const participant of participants) {
    const key = getParticipantStableKey(participant);
    const existing = byUser.get(key);
    if (!existing || compareParticipants(participant, existing) < 0) {
      byUser.set(key, participant);
    }
  }
  return sortPresenceParticipants(Array.from(byUser.values()));
}

export function filterParticipantsByPage(participants: PresenceParticipant[], page: string) {
  return participants.filter((participant) => getPresencePage(participant) === page);
}

export function mapPresenceByDocument(
  participants: PresenceParticipant[],
  options: MapPresenceByDocumentOptions = {},
) {
  const { currentUserId = null, currentClientId = null } = options;
  const byDocument = new Map<string, Map<string, PresenceParticipant[]>>();

  participants.forEach((participant) => {
    const documentId = getSelectedDocumentId(participant);
    if (!documentId) return;

    const byUser = byDocument.get(documentId) ?? new Map<string, PresenceParticipant[]>();
    const userKey = getParticipantStableKey(participant);
    const existing = byUser.get(userKey) ?? [];
    if (!existing.some((entry) => entry.client_id === participant.client_id)) {
      existing.push(participant);
    }
    byUser.set(userKey, existing);
    byDocument.set(documentId, byUser);
  });

  const resolved = new Map<string, DocumentPresenceEntry[]>();
  byDocument.forEach((byUser, documentId) => {
    const entries = Array.from(byUser.values())
      .map((userParticipants) => {
        const sortedByRank = sortPresenceParticipants(userParticipants);
        const representative = sortedByRank[0];
        if (!representative) return null;
        return {
          participant: representative,
          isCurrentUser: Boolean(currentUserId && representative.user_id === currentUserId),
          isCurrentClient: Boolean(
            currentClientId &&
              userParticipants.some((entry) => entry.client_id === currentClientId),
          ),
          tabCountForUser: userParticipants.length,
        } satisfies DocumentPresenceEntry;
      })
      .filter((entry): entry is DocumentPresenceEntry => Boolean(entry))
      .sort((a, b) => {
        const aPriority = a.isCurrentUser ? 0 : 1;
        const bPriority = b.isCurrentUser ? 0 : 1;
        if (aPriority !== bPriority) return aPriority - bPriority;
        return compareParticipants(a.participant, b.participant);
      });

    resolved.set(documentId, entries);
  });

  return resolved;
}
