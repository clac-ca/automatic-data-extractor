export type EventRecord = {
  readonly event?: string;
  readonly type?: string; // legacy/compat
  readonly event_id?: string;
  readonly engine_run_id?: string;
  readonly timestamp?: string | number | Date;
  readonly created_at?: string | number | Date; // legacy/compat
  readonly level?: string;
  readonly message?: string;
  readonly data?: Record<string, unknown> | null;
  readonly payload?: Record<string, unknown> | null; // legacy/compat
  readonly error?: Record<string, unknown> | null;
  readonly sequence?: number;
  readonly sse_id?: string;
  readonly _raw?: string;
};

export type RunStreamEvent = EventRecord;

export function isEventRecord(event: unknown): event is EventRecord {
  if (!event || typeof event !== "object") {
    return false;
  }
  const record = event as Record<string, unknown>;
  const ts = record.timestamp ?? record.created_at;
  const hasTimestamp =
    typeof ts === "string" || typeof ts === "number" || ts instanceof Date;
  const name = record.event ?? record.type;
  return typeof name === "string" && hasTimestamp;
}

export function eventTimestamp(event: EventRecord): string {
  const value = event.timestamp ?? event.created_at;
  const date = new Date(value as unknown as string);
  if (Number.isNaN(date.getTime())) {
    return new Date().toISOString();
  }
  return date.toISOString();
}

export function eventName(event: EventRecord): string {
  return (event.event ?? event.type ?? "").toString();
}

export function eventPayload(event: EventRecord): Record<string, unknown> {
  const payload = event.data ?? event.payload;
  if (payload && typeof payload === "object") {
    return payload as Record<string, unknown>;
  }
  return {};
}

export type RunStatus = import("@schema").RunStatus;
