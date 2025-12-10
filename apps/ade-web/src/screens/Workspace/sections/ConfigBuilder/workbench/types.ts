import type { RunSummary } from "@schema";
import type { RunStreamEvent, RunStatus } from "@shared/runs/types";

export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  size?: number | null;
  modifiedAt?: string | null;
  contentType?: string | null;
  etag?: string | null;
}

export interface WorkbenchFileNode {
  id: string;
  name: string;
  kind: WorkbenchFileKind;
  language?: string;
  children?: WorkbenchFileNode[];
  metadata?: WorkbenchFileMetadata | null;
}

export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  id: string;
  name: string;
  language?: string;
  initialContent: string;
  content: string;
  status: WorkbenchFileTabStatus;
  error?: string | null;
  etag?: string | null;
  metadata?: WorkbenchFileMetadata | null;
  pinned?: boolean;
  saving?: boolean;
  saveError?: string | null;
  lastSavedAt?: string | null;
}

export type WorkbenchConsoleLevel = "info" | "success" | "warning" | "error";

export interface WorkbenchConsoleLine {
  readonly id?: string;
  readonly level: WorkbenchConsoleLevel;
  readonly message: string;
  readonly origin?: "run" | "build" | "raw";
  readonly timestamp?: string;
  readonly raw?: unknown;
}

export interface WorkbenchValidationMessage {
  readonly level: "info" | "warning" | "error";
  readonly message: string;
  readonly path?: string;
}

export interface WorkbenchDataSeed {
  readonly tree: WorkbenchFileNode;
  readonly content: Record<string, string>;
  readonly console?: readonly WorkbenchConsoleLine[];
  readonly validation?: readonly WorkbenchValidationMessage[];
}

export interface WorkbenchValidationState {
  readonly status: "idle" | "running" | "success" | "error";
  readonly messages: readonly WorkbenchValidationMessage[];
  readonly lastRunAt?: string;
  readonly error?: string | null;
  readonly digest?: string | null;
}

export interface WorkbenchRunSummary {
  readonly runId: string;
  readonly status: RunStatus;
  readonly outputUrl?: string;
  readonly outputReady?: boolean;
  readonly outputFilename?: string | null;
  readonly outputPath?: string | null;
  readonly logsUrl?: string;
  readonly processedFile?: string | null;
  readonly outputLoaded: boolean;
  readonly summary?: RunSummary | null;
  readonly summaryLoaded: boolean;
  readonly summaryError?: string | null;
  readonly telemetry?: readonly RunStreamEvent[] | null;
  readonly telemetryLoaded: boolean;
  readonly telemetryError?: string | null;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
  readonly error?: string | null;
  readonly startedAt?: string | null;
  readonly completedAt?: string | null;
  readonly durationMs?: number | null;
}
