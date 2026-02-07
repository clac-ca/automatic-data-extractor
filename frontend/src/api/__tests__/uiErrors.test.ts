import { describe, expect, it } from "vitest";

import { ApiError, type ProblemDetails } from "@/api/errors";
import { mapUiError } from "@/api/uiErrors";

function asProblemDetails(value: unknown): ProblemDetails {
  return value as ProblemDetails;
}

describe("mapUiError", () => {
  it("uses generic fallback for unknown values", () => {
    expect(mapUiError(null, { fallback: "Unable to save." }).message).toBe("Unable to save.");
  });

  it("returns a safe message for etag conflicts", () => {
    const apiError = new ApiError("etag mismatch", 412);

    const mapped = mapUiError(apiError, { fallback: "Unable to save." });

    expect(mapped.message).toBe("This record changed while you were editing. Refresh and try again.");
    expect(mapped.status).toBe(412);
  });

  it("collects field-level problem details", () => {
    const problem = asProblemDetails({
      type: "about:blank",
      title: "Unprocessable Content",
      status: 422,
      instance: "/api/v1/admin/sso/providers",
      errors: [
        { path: "label", message: "Label is required.", code: "required" },
        { path: "issuer", message: "Issuer must be a URL.", code: "invalid" },
      ],
    });

    const mapped = mapUiError(new ApiError("Validation failed", 422, problem), {
      fallback: "Unable to save provider.",
    });

    expect(mapped.fieldErrors.label).toEqual(["Label is required."]);
    expect(mapped.fieldErrors.issuer).toEqual(["Issuer must be a URL."]);
  });
});
