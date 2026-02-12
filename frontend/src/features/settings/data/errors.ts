import { mapUiError } from "@/api/uiErrors";
import type { ProblemDetailsErrorMap } from "@/api/errors";

export interface NormalizedSettingsError {
  readonly message: string;
  readonly fieldErrors: ProblemDetailsErrorMap;
}

export function normalizeSettingsError(
  error: unknown,
  fallback: string,
): NormalizedSettingsError {
  const mapped = mapUiError(error, { fallback });
  return {
    message: mapped.message,
    fieldErrors: mapped.fieldErrors,
  };
}
