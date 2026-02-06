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
});
