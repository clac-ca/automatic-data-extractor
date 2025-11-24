import { ADE_TELEMETRY_EVENT_SCHEMA } from "@schema/adeTelemetry";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export type RunEvent =
  | RunCreatedEvent
  | RunStartedEvent
  | RunLogEvent
  | RunCompletedEvent;

export interface RunEventBase {
  readonly object: "ade.run.event";
  readonly run_id: string;
  readonly created: number;
  readonly type: RunEvent["type"];
}

export interface RunCreatedEvent extends RunEventBase {
  readonly type: "run.created";
  readonly status: RunStatus;
  readonly config_id: string;
}

export interface RunStartedEvent extends RunEventBase {
  readonly type: "run.started";
}

export interface RunLogEvent extends RunEventBase {
  readonly type: "run.log";
  readonly stream: "stdout" | "stderr";
  readonly message: string;
}

export interface RunCompletedEvent extends RunEventBase {
  readonly type: "run.completed";
  readonly status: RunStatus;
  readonly exit_code?: number | null;
  readonly error_message?: string | null;
  readonly artifact_path?: string | null;
  readonly events_path?: string | null;
  readonly output_paths?: string[];
  readonly processed_files?: string[];
}

export type RunStreamEvent = RunEvent | TelemetryEnvelope;

export function isTelemetryEnvelope(event: RunStreamEvent): event is TelemetryEnvelope {
  return (event as TelemetryEnvelope).schema === ADE_TELEMETRY_EVENT_SCHEMA;
}
