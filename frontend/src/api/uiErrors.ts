import { ApiError, type ProblemDetailsErrorMap, groupProblemDetailsErrors } from "@/api/errors";

type UiStatusMessageMap = Partial<Record<number, string>>;

export interface UiErrorResult {
  readonly message: string;
  readonly status?: number;
  readonly fieldErrors: ProblemDetailsErrorMap;
}

const DEFAULT_STATUS_MESSAGES: Record<number, string> = {
  400: "The request is invalid. Review your inputs and try again.",
  401: "Your session has expired. Sign in again and retry.",
  403: "You do not have permission to perform this action.",
  409: "This record was changed by another user. Refresh and retry.",
  412: "This record changed while you were editing. Refresh and try again.",
  422: "One or more fields are invalid. Correct them and retry.",
};

const ETAG_MISMATCH_PATTERN = /etag mismatch/i;

export function mapUiError(
  error: unknown,
  options: {
    readonly fallback: string;
    readonly statusMessages?: UiStatusMessageMap;
  },
): UiErrorResult {
  const fallback = options.fallback;
  const statusMessages = { ...DEFAULT_STATUS_MESSAGES, ...(options.statusMessages ?? {}) };
  if (!(error instanceof ApiError)) {
    if (error instanceof Error && error.message.trim().length > 0) {
      return { message: error.message, fieldErrors: {} };
    }
    return { message: fallback, fieldErrors: {} };
  }

  const status = error.status;
  const fieldErrors = groupProblemDetailsErrors(error.problem?.errors);
  const defaultStatusMessage = statusMessages[status];
  const rawMessage = error.message?.trim() || "";

  if (!rawMessage || ETAG_MISMATCH_PATTERN.test(rawMessage)) {
    return {
      message: defaultStatusMessage ?? fallback,
      status,
      fieldErrors,
    };
  }

  return {
    message: rawMessage,
    status,
    fieldErrors,
  };
}
