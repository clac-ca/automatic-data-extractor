export type EventRecord = {
  readonly event: string;
  readonly event_id?: string;
  readonly engine_run_id?: string;
  readonly timestamp: string | number | Date;
  readonly level?: string;
  readonly message?: string;
  readonly data?: Record<string, unknown> | null;
  readonly error?: Record<string, unknown> | null;
  readonly _raw?: string;
};

export type RunStreamEvent = EventRecord;

export function eventTimestamp(event: EventRecord): string {
  const date = new Date(event.timestamp);
  if (Number.isNaN(date.getTime())) {
    return new Date().toISOString();
  }
  return date.toISOString();
}

export function eventName(event: EventRecord): string {
  return event.event.toString();
}

export function eventPayload(event: EventRecord): Record<string, unknown> {
  const payload = event.data;
  if (payload && typeof payload === "object") {
    return payload as Record<string, unknown>;
  }
  return {};
}

export type RunStatus = import("@schema").RunStatus;
