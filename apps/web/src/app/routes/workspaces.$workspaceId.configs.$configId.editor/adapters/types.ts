export type FileKind = "file" | "folder";

export type FileMime = "text/x-python" | "application/json" | "text/plain" | "text/x-shellscript";

export interface FileNode {
  readonly path: string;
  readonly name: string;
  readonly kind: FileKind;
  readonly parent: string | null;
  readonly children: FileNode[];
  readonly mime?: FileMime;
  readonly size?: number;
  readonly etag?: string;
}

export interface FileBuffer {
  readonly path: string;
  readonly content: string;
  readonly mime: FileMime;
  readonly etag?: string;
}

export interface Problem {
  readonly path: string;
  readonly message: string;
  readonly severity: "error" | "warning" | "info";
  readonly line?: number;
  readonly column?: number;
}

export interface RunLogLine {
  readonly ts: string;
  readonly text: string;
}

export interface ValidationResult {
  readonly problems: readonly Problem[];
  readonly logs: readonly RunLogLine[];
}

export interface RunResult {
  readonly logs: readonly RunLogLine[];
}

export type AdapterWriteOptions = {
  readonly ifMatch?: string;
};

export function detectLanguageFromPath(path: string): string {
  if (path.endsWith(".py")) {
    return "python";
  }
  if (path.endsWith(".json")) {
    return "json";
  }
  if (path.endsWith(".toml")) {
    return "toml";
  }
  if (path.endsWith(".env")) {
    return "shell";
  }
  if (path.endsWith(".yml") || path.endsWith(".yaml")) {
    return "yaml";
  }
  return "plaintext";
}

export function detectMimeFromPath(path: string): FileMime {
  if (path.endsWith(".py")) {
    return "text/x-python";
  }
  if (path.endsWith(".json")) {
    return "application/json";
  }
  if (path.endsWith(".env")) {
    return "text/x-shellscript";
  }
  return "text/plain";
}
