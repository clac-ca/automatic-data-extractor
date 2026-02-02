import type { components } from "@/types";

export type ProblemDetailsErrorItem = components["schemas"]["ProblemDetailsErrorItem"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];
export type ProblemDetailsErrorMap = Record<string, string[]>;

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
