import type { AdminSettingsReadResponse } from "@/api/admin/settings";
import { ApiError, type ProblemDetailsErrorMap } from "@/api/errors";

export type RuntimeSettingFieldMeta = AdminSettingsReadResponse["meta"]["safeMode"]["enabled"];

export function collectRuntimeSettingFieldMeta(
  settings: AdminSettingsReadResponse,
): readonly RuntimeSettingFieldMeta[] {
  return [
    settings.meta.safeMode.enabled,
    settings.meta.safeMode.detail,
    settings.meta.auth.mode,
    settings.meta.auth.password.resetEnabled,
    settings.meta.auth.password.mfaRequired,
    settings.meta.auth.password.complexity.minLength,
    settings.meta.auth.password.complexity.requireUppercase,
    settings.meta.auth.password.complexity.requireLowercase,
    settings.meta.auth.password.complexity.requireNumber,
    settings.meta.auth.password.complexity.requireSymbol,
    settings.meta.auth.password.lockout.maxAttempts,
    settings.meta.auth.password.lockout.durationSeconds,
    settings.meta.auth.identityProvider.provisioningMode,
  ];
}

export function collectLockedEnvVars(settings: AdminSettingsReadResponse): string[] {
  return Array.from(
    new Set(
      collectRuntimeSettingFieldMeta(settings)
        .filter((field) => field.lockedByEnv && field.envVar)
        .map((field) => field.envVar as string),
    ),
  ).sort((left, right) => left.localeCompare(right));
}

export function findRuntimeSettingFieldError(
  fieldErrors: ProblemDetailsErrorMap,
  path: string,
): string | undefined {
  const snakePath = path.replaceAll(".", "_");
  const candidates = [path, `body.${path}`, snakePath, `body.${snakePath}`];
  for (const candidate of candidates) {
    const match = fieldErrors[candidate]?.[0];
    if (match) {
      return match;
    }
  }
  return undefined;
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

export function formatRuntimeSettingsTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}
