export type AdeEvent = {
  readonly object: "ade.event";
  readonly schema?: string;
  readonly version?: string;
  readonly type: string; // e.g. run.created, run.log.delta, build.completed
  readonly created_at: string;
  readonly workspace_id?: string | null;
  readonly configuration_id?: string | null;
  readonly run_id?: string | null;
  readonly build_id?: string | null;
  readonly run?: Record<string, unknown> | null;
  readonly build?: Record<string, unknown> | null;
  readonly env?: Record<string, unknown> | null;
  readonly validation?: Record<string, unknown> | null;
  readonly execution?: Record<string, unknown> | null;
  readonly output_delta?: Record<string, unknown> | null;
  readonly log?: { stream?: string; message?: string; [key: string]: unknown } | null;
  readonly error?: Record<string, unknown> | null;
};

export type RunStreamEvent = AdeEvent;

export function isAdeEvent(event: unknown): event is AdeEvent {
  return Boolean(
    event &&
      typeof event === "object" &&
      (event as Record<string, unknown>).object === "ade.event" &&
      typeof (event as Record<string, unknown>).type === "string",
  );
}

export function eventTimestamp(event: AdeEvent): number {
  const value = event.created_at;
  const ts = typeof value === "number" ? value * 1000 : Date.parse(String(value));
  return Number.isFinite(ts) ? ts : Date.now();
}
