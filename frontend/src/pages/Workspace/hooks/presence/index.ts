export { usePresenceChannel } from "./usePresenceChannel";
export {
  dedupePresenceParticipants,
  filterParticipantsByPage,
  getPresencePage,
  getPresenceParticipantLabel,
  getSelectedDocumentId,
  mapPresenceByDocument,
  rankPresenceParticipant,
  sortPresenceParticipants,
} from "./presenceParticipants";
export type { DocumentPresenceEntry } from "./presenceParticipants";
export type { PresenceConnectionState, PresenceContext, PresenceParticipant } from "@/types/presence";
