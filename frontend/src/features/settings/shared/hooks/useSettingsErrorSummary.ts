import { useCallback, useMemo, useState } from "react";

import type { ProblemDetailsErrorMap } from "@/api/errors";

import type { SettingsFormErrorSummaryModel } from "../types";

export interface UseSettingsErrorSummaryOptions {
  readonly title?: string;
  readonly fieldIdByKey: Record<string, string>;
  readonly fieldLabelByKey?: Record<string, string>;
}

function firstError(errors: readonly string[] | undefined) {
  if (!errors || errors.length === 0) {
    return null;
  }
  return errors[0]?.trim() || null;
}

export function useSettingsErrorSummary({
  title = "Fix the following fields before continuing.",
  fieldIdByKey,
  fieldLabelByKey = {},
}: UseSettingsErrorSummaryOptions) {
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const summary = useMemo<SettingsFormErrorSummaryModel | null>(() => {
    const items = Object.entries(fieldErrors)
      .filter(([, message]) => message.trim().length > 0)
      .map(([key, message]) => ({
        key,
        label: fieldLabelByKey[key] ?? key,
        message,
        fieldId: fieldIdByKey[key],
      }));

    if (items.length === 0) {
      return null;
    }

    return {
      title,
      items,
    };
  }, [fieldErrors, fieldIdByKey, fieldLabelByKey, title]);

  const clearErrors = useCallback(() => {
    setFieldErrors({});
  }, []);

  const setClientErrors = useCallback((errors: Record<string, string>) => {
    const normalized = Object.fromEntries(
      Object.entries(errors).filter(([, value]) => value.trim().length > 0),
    );
    setFieldErrors(normalized);
  }, []);

  const setProblemErrors = useCallback((errors: ProblemDetailsErrorMap) => {
    const normalized = Object.fromEntries(
      Object.entries(errors)
        .map(([key, values]) => [key, firstError(values)])
        .filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    setFieldErrors(normalized);
  }, []);

  const getFieldError = useCallback(
    (fieldKey: string) => {
      return fieldErrors[fieldKey] ?? undefined;
    },
    [fieldErrors],
  );

  return {
    summary,
    fieldErrors,
    getFieldError,
    setClientErrors,
    setProblemErrors,
    clearErrors,
  };
}
