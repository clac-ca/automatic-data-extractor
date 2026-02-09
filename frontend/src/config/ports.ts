export const DEFAULT_WEB_PORT = 8000;

export const parsePortFromEnv = (
  value: string | undefined,
  { envVar, fallback }: { envVar: string; fallback: number },
): number => {
  if (typeof value !== "string") {
    return fallback;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return fallback;
  }
  const parsed = Number.parseInt(trimmed, 10);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error(`${envVar} must be an integer between 1 and 65535 (got "${value}").`);
  }
  return parsed;
};
