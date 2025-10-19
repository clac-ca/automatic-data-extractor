export type RequiredEnvKey = "VITE_API_BASE_URL";

export function getEnv(name: RequiredEnvKey) {
  const value = import.meta.env[name];
  if (typeof value === "undefined") {
    throw new Error(`Missing environment variable: ${name}`);
  }
  return value;
}

export function getOptionalEnv(name: string, fallback: string) {
  const value = import.meta.env[name];
  if (typeof value === "string" && value.length > 0) {
    return value;
  }
  return fallback;
}
