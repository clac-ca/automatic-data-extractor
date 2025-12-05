import type { components } from "@schema";

type EventSchema = components["schemas"]["AdeEventV1"];

export type AdeEvent = EventSchema;
export type AdeEventPayload = NonNullable<EventSchema["payload"]>;
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
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return new Date().toISOString();
  }
  return date.toISOString();
}

export type RunStatus = import("@schema").RunStatus;
