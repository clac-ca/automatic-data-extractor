export type PresenceContext = Record<string, unknown>;

export type PresenceParticipant = {
  client_id: string;
  user_id: string;
  display_name?: string | null;
  email?: string | null;
  status?: string | null;
  presence?: Record<string, unknown> | null;
  selection?: Record<string, unknown> | null;
  editing?: Record<string, unknown> | null;
};

export type PresenceConnectionState = "idle" | "connecting" | "open" | "closed";
