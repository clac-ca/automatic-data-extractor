import type { components } from "@/types";

export type ProblemDetailsErrorItem = components["schemas"]["ProblemDetailsErrorItem"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];
export type ProblemDetailsErrorMap = Record<string, string[]>;

const CONFIG_IMPORT_ERROR_CODES = new Set([
  "file_too_large",
  "archive_too_large",
  "invalid_archive",
  "archive_empty",
  "too_many_entries",
  "path_not_allowed",
  "github_url_invalid",
  "github_not_found_or_private",
  "github_rate_limited",
  "github_download_failed",
]);

const ERROR_CODE_MESSAGES: Record<string, string> = {
  engine_dependency_missing:
    "Configuration must declare ade-engine in its dependency manifests before it can be validated, published, or run.",
  input_document_required_for_process:
    "A document is required when creating a process run.",
};

export function groupProblemDetailsErrors(
  errors: ProblemDetailsErrorItem[] | null | undefined,
): ProblemDetailsErrorMap {
  const grouped: ProblemDetailsErrorMap = {};
  if (!errors) {
    return grouped;
  }
  for (const error of errors) {
    const path = error.path?.trim();
    if (!path) {
      continue;
    }
    if (!grouped[path]) {
      grouped[path] = [];
    }
    grouped[path].push(error.message);
  }
  return grouped;
}

export function isProblemDetailsContentType(contentType: string): boolean {
  return contentType.includes("application/problem+json") || contentType.includes("application/json");
}

export async function tryParseProblemDetails(response: Response): Promise<ProblemDetails | undefined> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!isProblemDetailsContentType(contentType)) {
    return undefined;
  }
  try {
    return (await response.clone().json()) as ProblemDetails;
  } catch {
    return undefined;
  }
}

type ProblemLike = {
  title?: unknown;
  detail?: unknown;
  status?: unknown;
};

type ProblemDetailShape = {
  code?: string;
  message?: string;
  limit?: number;
};

const LIMIT_PATTERN = /\(limit=(\d+)\)\s*$/i;
const SIMPLE_CODE_PATTERN = /^[a-z0-9_]+$/i;

function parseLimit(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.floor(value);
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.floor(parsed);
    }
  }
  return undefined;
}

function parseProblemDetail(detail: unknown): ProblemDetailShape {
  if (typeof detail === "string") {
    const text = detail.trim();
    const limitMatch = text.match(LIMIT_PATTERN);
    const limit = limitMatch?.[1] ? parseLimit(limitMatch[1]) : undefined;
    return {
      code: SIMPLE_CODE_PATTERN.test(text) ? text : undefined,
      message: text,
      limit,
    };
  }
  if (!detail || typeof detail !== "object") {
    return {};
  }

  const payload = detail as Record<string, unknown>;
  const directError = payload.error;

  let code: string | undefined;
  let message: string | undefined;
  const limit = parseLimit(payload.limit);

  if (typeof directError === "string") {
    code = directError;
  } else if (directError && typeof directError === "object") {
    const errorObject = directError as Record<string, unknown>;
    if (typeof errorObject.code === "string") {
      code = errorObject.code;
    }
    if (typeof errorObject.message === "string") {
      message = errorObject.message;
    }
  }

  if (!message && typeof payload.detail === "string") {
    message = payload.detail;
  }
  if (!message && typeof payload.message === "string") {
    message = payload.message;
  }

  return { code, message, limit };
}

function parseProblemErrors(problem: ProblemDetails | undefined): ProblemDetailShape {
  const errors = (problem as { errors?: ProblemDetailsErrorItem[] } | undefined)?.errors;
  if (!Array.isArray(errors) || errors.length === 0) {
    return {};
  }
  for (const item of errors) {
    const code = typeof item.code === "string" && item.code.trim().length > 0 ? item.code.trim() : undefined;
    const message =
      typeof item.message === "string" && item.message.trim().length > 0
        ? item.message.trim()
        : undefined;
    if (code || message) {
      const limitMatch = message?.match(LIMIT_PATTERN);
      const limit = limitMatch?.[1] ? parseLimit(limitMatch[1]) : undefined;
      return { code, message, limit };
    }
  }
  return {};
}

function parseProblem(problem: ProblemDetails | undefined): ProblemDetailShape {
  if (!problem) {
    return {};
  }
  const candidate = problem as unknown as ProblemLike;
  const detailShape = parseProblemDetail(candidate.detail);
  const errorsShape = parseProblemErrors(problem);
  return {
    code: detailShape.code ?? errorsShape.code,
    message: detailShape.message ?? errorsShape.message,
    limit: detailShape.limit ?? errorsShape.limit,
  };
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    const mb = bytes / (1024 * 1024);
    return `${Number.isInteger(mb) ? mb : mb.toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    const kb = bytes / 1024;
    return `${Number.isInteger(kb) ? kb : kb.toFixed(1)} KB`;
  }
  return `${bytes} B`;
}

function extractImportPath(message: string | undefined, code: string): string | undefined {
  if (!message) {
    return undefined;
  }
  const cleaned = message.replace(LIMIT_PATTERN, "").trim();
  if (!cleaned || cleaned === code || cleaned.includes(" ")) {
    return undefined;
  }
  return cleaned;
}

function buildConfigImportErrorMessage(parsed: ProblemDetailShape): string {
  const code = parsed.code ?? "";
  const limitText = parsed.limit ? ` Limit: ${formatBytes(parsed.limit)}.` : "";
  const pathText = (() => {
    const path = extractImportPath(parsed.message, code);
    return path ? ` File: ${path}.` : "";
  })();

  switch (code) {
    case "file_too_large":
      return `The zip contains a file that is too large to import.${limitText}${pathText}`;
    case "archive_too_large":
      return `The zip archive is too large to import.${limitText}`;
    case "invalid_archive":
      return "The uploaded file is not a valid zip archive.";
    case "archive_empty":
      return "The zip archive is empty or does not contain importable files.";
    case "too_many_entries":
      return "The zip archive contains too many files to import safely.";
    case "path_not_allowed":
      return `The zip archive includes unsupported file paths.${pathText}`;
    case "github_url_invalid":
      return "Enter a valid GitHub repository URL.";
    case "github_not_found_or_private":
      return (
        "Repository not found or private. Private repositories are not supported. " +
        "Use GitHub Download ZIP and import the ZIP file."
      );
    case "github_rate_limited":
      return "GitHub rate limit reached. Please wait and try again.";
    case "github_download_failed":
      return "GitHub download failed. Please try again in a moment.";
    default:
      return parsed.message ?? "Unable to import configuration archive.";
  }
}

export function buildApiErrorMessage(problem: ProblemDetails | undefined, status: number): string {
  const parsed = parseProblem(problem);
  if (parsed.code && CONFIG_IMPORT_ERROR_CODES.has(parsed.code)) {
    return buildConfigImportErrorMessage(parsed);
  }
  if (parsed.code && ERROR_CODE_MESSAGES[parsed.code]) {
    return parsed.message ?? ERROR_CODE_MESSAGES[parsed.code];
  }
  if (parsed.message) {
    return parsed.message;
  }

  const title = (problem as unknown as ProblemLike | undefined)?.title;
  if (typeof title === "string" && title.trim().length > 0) {
    return title;
  }
  return `Request failed with status ${status}`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly problem?: ProblemDetails;

  constructor(message: string, status: number, problem?: ProblemDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

export function hasProblemCode(error: unknown, code: string): boolean {
  if (!(error instanceof ApiError)) {
    return false;
  }
  const errors = error.problem?.errors;
  if (!errors || errors.length === 0) {
    return false;
  }
  return errors.some((item) => item.code === code);
}
