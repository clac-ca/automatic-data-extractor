import type { ProblemDetails } from "../api/types";

export type FieldErrors<TField extends string> = Partial<Record<TField, string>>;

export function hasFieldErrors<TField extends string>(errors: FieldErrors<TField>) {
  return Object.values(errors).some((value) => Boolean(value));
}

export function parseProblemErrors(problem?: ProblemDetails | null) {
  if (!problem?.errors) {
    return {} as Record<string, string>;
  }

  const result: Record<string, string> = {};

  for (const [field, messages] of Object.entries(problem.errors)) {
    if (Array.isArray(messages) && messages.length > 0) {
      result[field] = messages.join(" ");
    }
  }

  return result;
}
