import telemetrySchema from "../../../../ade-engine/src/ade_engine/schemas/telemetry.event.v1.schema.json";

export const ADE_TELEMETRY_EVENT_SCHEMA =
  telemetrySchema.properties?.schema?.const ?? "ade.telemetry/run-event.v1";

export type TelemetryLevel = "debug" | "info" | "warning" | "error" | "critical";

export interface TelemetryEventPayload {
  readonly event: string;
  readonly level: TelemetryLevel;
  readonly [key: string]: unknown;
}

export interface TelemetryEnvelope {
  readonly schema: typeof ADE_TELEMETRY_EVENT_SCHEMA;
  readonly version: string;
  readonly run_request_id?: string;
  readonly run_id?: string | null;
  readonly timestamp: string;
  readonly event: TelemetryEventPayload;
}

export { telemetrySchema };
