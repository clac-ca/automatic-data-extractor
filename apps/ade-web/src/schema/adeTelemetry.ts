// Hard-coded copy of ade-engine telemetry event schema (kept local to avoid cross-package import).
// TODO figure out a longer-term solution.  Ideally Id prefer not to have ade-web depend on ade-engine directly.
export const telemetrySchema = {
  $id: "urn:ade:telemetry.event.v1",
  $schema: "https://json-schema.org/draft/2020-12/schema",
  title: "ADE telemetry event envelope",
  type: "object",
  properties: {
    schema: {
      type: "string",
      const: "ade.telemetry/run-event.v1",
      default: "ade.telemetry/run-event.v1",
    },
    version: { type: "string" },
    run_id: { type: "string" },
    timestamp: { type: "string", format: "date-time" },
    metadata: { type: "object", additionalProperties: true },
    event: {
      type: "object",
      required: ["event", "level"],
      properties: {
        event: { type: "string" },
        level: { type: "string", enum: ["debug", "info", "warning", "error", "critical"] },
        payload: { type: "object", additionalProperties: true },
      },
      additionalProperties: true,
    },
  },
  required: ["schema", "version", "run_id", "timestamp", "event"],
  additionalProperties: true,
} as const;

export const ADE_TELEMETRY_EVENT_SCHEMA =
  telemetrySchema.properties?.schema?.default ?? "ade.telemetry/run-event.v1";

export type TelemetryLevel = "debug" | "info" | "warning" | "error" | "critical";

export interface TelemetryEventPayload {
  readonly event: string;
  readonly level: TelemetryLevel;
  readonly payload?: Record<string, unknown>;
  readonly [key: string]: unknown;
}

export interface TelemetryEnvelope {
  readonly schema: typeof ADE_TELEMETRY_EVENT_SCHEMA;
  readonly version: string;
  readonly run_id: string;
  readonly timestamp: string;
  readonly metadata?: Record<string, unknown>;
  readonly event: TelemetryEventPayload;
}

export { telemetrySchema };
