export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  readonly size?: number | null;
  readonly modifiedAt?: string | null;
  readonly contentType?: string | null;
  readonly etag?: string | null;
}

export interface WorkbenchFileNode {
  readonly id: string;
  readonly name: string;
  readonly kind: WorkbenchFileKind;
  readonly language?: string;
  readonly children?: readonly WorkbenchFileNode[];
  readonly metadata?: WorkbenchFileMetadata;
}

export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  readonly id: string;
  readonly name: string;
  readonly language?: string;
  readonly initialContent: string;
  readonly content: string;
  readonly status: WorkbenchFileTabStatus;
  readonly error?: string | null;
  readonly etag?: string | null;
  readonly metadata?: WorkbenchFileMetadata;
}

export type WorkbenchConsoleLevel = "info" | "success" | "warning" | "error";

export interface WorkbenchConsoleLine {
  readonly level: WorkbenchConsoleLevel;
  readonly message: string;
  readonly timestamp?: string;
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
