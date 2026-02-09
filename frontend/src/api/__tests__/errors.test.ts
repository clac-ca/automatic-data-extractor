import { describe, expect, it } from "vitest";

import { buildApiErrorMessage, type ProblemDetails } from "@/api/errors";

function asProblemDetails(value: unknown): ProblemDetails {
  return value as ProblemDetails;
}

describe("buildApiErrorMessage", () => {
  it("returns engine dependency detail when provided", () => {
    const problem = asProblemDetails({
      type: "about:blank",
      title: "Unprocessable Content",
      status: 422,
      instance: "/api/v1/workspaces/ws/configurations/cfg/validate",
      detail: {
        error: "engine_dependency_missing",
        detail: "Configuration must declare ade-engine in dependency manifests.",
      },
    });

    const message = buildApiErrorMessage(problem, 422);

    expect(message).toBe("Configuration must declare ade-engine in dependency manifests.");
  });

  it("maps engine dependency code to a user-facing fallback message", () => {
    const problem = asProblemDetails({
      type: "about:blank",
      title: "Unprocessable Content",
      status: 422,
      instance: "/api/v1/workspaces/ws/runs",
      detail: {
        error: "engine_dependency_missing",
      },
    });

    const message = buildApiErrorMessage(problem, 422);

    expect(message).toContain("Configuration must declare ade-engine");
  });

  it("falls back to title and status when detail is unavailable", () => {
    const titled = asProblemDetails({
      type: "about:blank",
      title: "Bad Request",
      status: 400,
      instance: "/api/v1/test",
    });
    const untitled = asProblemDetails({
      type: "about:blank",
      title: "",
      status: 500,
      instance: "/api/v1/test",
    });

    expect(buildApiErrorMessage(titled, 400)).toBe("Bad Request");
    expect(buildApiErrorMessage(untitled, 500)).toBe("Request failed with status 500");
  });

  it("maps config import file size errors to a friendly message", () => {
    const problem = asProblemDetails({
      type: "bad_request",
      title: "Bad request",
      status: 400,
      instance: "/api/v1/workspaces/ws/configurations/import",
      detail: "logs/too_big.ndjson (limit=52428800)",
      errors: [{ message: "logs/too_big.ndjson", code: "file_too_large" }],
    });

    const message = buildApiErrorMessage(problem, 400);

    expect(message).toContain("too large to import");
    expect(message).toContain("50 MB");
    expect(message).toContain("logs/too_big.ndjson");
  });

  it("maps archive size errors with limit from structured detail", () => {
    const problem = asProblemDetails({
      type: "bad_request",
      title: "Bad request",
      status: 413,
      instance: "/api/v1/workspaces/ws/configurations/import",
      detail: { error: "archive_too_large", limit: 73400320 },
    });

    const message = buildApiErrorMessage(problem, 413);

    expect(message).toContain("archive is too large");
    expect(message).toContain("70 MB");
  });

  it("maps github invalid URL errors", () => {
    const problem = asProblemDetails({
      type: "bad_request",
      title: "Bad request",
      status: 400,
      instance: "/api/v1/workspaces/ws/configurations/import/github",
      detail: { error: "github_url_invalid" },
    });

    const message = buildApiErrorMessage(problem, 400);

    expect(message).toContain("valid GitHub repository URL");
  });

  it("maps github not found/private errors", () => {
    const problem = asProblemDetails({
      type: "bad_request",
      title: "Bad request",
      status: 400,
      instance: "/api/v1/workspaces/ws/configurations/import/github",
      detail: { error: "github_not_found_or_private" },
    });

    const message = buildApiErrorMessage(problem, 400);

    expect(message).toContain("not found or private");
    expect(message).toContain("Download ZIP");
  });

  it("maps github rate limit errors", () => {
    const problem = asProblemDetails({
      type: "bad_request",
      title: "Bad request",
      status: 429,
      instance: "/api/v1/workspaces/ws/configurations/import/github",
      detail: { error: "github_rate_limited" },
    });

    const message = buildApiErrorMessage(problem, 429);

    expect(message).toContain("rate limit");
  });
});
