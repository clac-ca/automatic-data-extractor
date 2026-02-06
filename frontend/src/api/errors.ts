import type { components } from "@/types";

export type ProblemDetailsErrorItem = components["schemas"]["ProblemDetailsErrorItem"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];
export type ProblemDetailsErrorMap = Record<string, string[]>;

const ERROR_CODE_MESSAGES: Record<string, string> = {
  engine_dependency_missing:
    "Configuration must declare ade-engine in its dependency manifests before it can be validated, published, or run.",
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
};

function parseProblemDetail(detail: unknown): ProblemDetailShape {
  if (typeof detail === "string") {
    return { code: detail, message: detail };
  }
  if (!detail || typeof detail !== "object") {
    return {};
  }

  const payload = detail as Record<string, unknown>;
  const directError = payload.error;

  let code: string | undefined;
  let message: string | undefined;

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

  return { code, message };
}

function parseProblem(problem: ProblemDetails | undefined): ProblemDetailShape {
  if (!problem) {
    return {};
  }
  const candidate = problem as unknown as ProblemLike;
  return parseProblemDetail(candidate.detail);
}

export function buildApiErrorMessage(problem: ProblemDetails | undefined, status: number): string {
  const parsed = parseProblem(problem);
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
