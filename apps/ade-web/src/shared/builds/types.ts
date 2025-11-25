export type BuildStatus = "queued" | "building" | "active" | "failed" | "canceled";

export type BuildEvent =
  | BuildCreatedEvent
  | BuildStepEvent
  | BuildLogEvent
  | BuildCompletedEvent;

export interface BuildEventBase {
  readonly object: "ade.build.event";
  readonly build_id: string;
  readonly created: number;
  readonly type: BuildEvent["type"];
}

export interface BuildCreatedEvent extends BuildEventBase {
  readonly type: "build.created";
  readonly status: BuildStatus;
  readonly configuration_id: string;
}

export interface BuildStepEvent extends BuildEventBase {
  readonly type: "build.step";
  readonly step:
    | "create_venv"
    | "upgrade_pip"
    | "install_engine"
    | "install_config"
    | "verify_imports"
    | "collect_metadata";
  readonly message?: string | null;
}

export interface BuildLogEvent extends BuildEventBase {
  readonly type: "build.log";
  readonly stream: "stdout" | "stderr";
  readonly message: string;
}

export interface BuildCompletedEvent extends BuildEventBase {
  readonly type: "build.completed";
  readonly status: BuildStatus;
  readonly exit_code?: number | null;
  readonly error_message?: string | null;
  readonly summary?: string | null;
}
