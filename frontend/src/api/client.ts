const DEFAULT_BASE_URL = "/api";

function normaliseBaseUrl(baseUrl: string | undefined): string {
  if (!baseUrl) {
    return DEFAULT_BASE_URL;
  }
  const trimmed = baseUrl.trim();
  if (!trimmed) {
    return DEFAULT_BASE_URL;
  }
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export const API_BASE_URL = normaliseBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
);
