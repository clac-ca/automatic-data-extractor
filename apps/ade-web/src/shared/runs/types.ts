import type { components } from "@schema";

export type AdeEvent = components["schemas"]["AdeEvent"];
export type AdeEventPayload = components["schemas"]["AdeEventPayload"];
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
