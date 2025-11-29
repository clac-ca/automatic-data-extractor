export type AdeEventPayload = Record<string, unknown> | null | undefined;

export type AdeEvent = {
  readonly type: string; // e.g. run.started, build.phase.completed, console.line
  readonly event_id?: string | null;
  readonly created_at: string | number | Date;
  readonly sequence?: number | null;

  readonly source?: string | null;

  readonly workspace_id?: string | null;
  readonly configuration_id?: string | null;
  readonly run_id?: string | null;
  readonly build_id?: string | null;

  readonly payload?: AdeEventPayload;

  // Legacy fields kept for backwards compatibility with older logs.
  readonly object?: string | null;
  readonly schema?: string | null;
  readonly version?: string | null;
  readonly [key: string]: unknown;
};

export type RunStreamEvent = AdeEvent;

export function isAdeEvent(event: unknown): event is AdeEvent {
  if (!event || typeof event !== "object") {
    return false;
  }
  const record = event as Record<string, unknown>;
  const createdAt = record.created_at;
  const hasTimestamp =
    typeof createdAt === "string" || typeof createdAt === "number" || createdAt instanceof Date;
  return typeof record.type === "string" && hasTimestamp;
}

export function eventTimestamp(event: AdeEvent): string {
  const value = event.created_at;
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    const ms = value > 1_000_000_000_000 ? value : value * 1000;
    return new Date(ms).toISOString();
  }
  return new Date().toISOString();
}
