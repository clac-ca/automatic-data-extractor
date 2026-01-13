import { normalizePathname } from "@app/navigation/paths";

export type LocationLike = {
  readonly pathname: string;
  readonly search: string;
  readonly hash: string;
};

export const DEFAULT_APP_HOME = "/workspaces";
export const DEFAULT_RETURN_TO = "/";

const PUBLIC_PATHS = new Set<string>(["/", "/login", "/setup", "/logout"]);

export function isPublicPath(path: string): boolean {
  if (!path) {
    return true;
  }

  const normalized = normalizePathname(path);

  if (PUBLIC_PATHS.has(normalized)) {
    return true;
  }
  return false;
}

export function joinPath(location: LocationLike): string {
  return `${location.pathname}${location.search}${location.hash}`;
}

export function normalizeNextFromLocation(location: LocationLike): string {
  const raw = joinPath(location) || "/";
  const sanitized = sanitizeNextPath(raw);
  return sanitized ?? DEFAULT_RETURN_TO;
}

export function sanitizeNextPath(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed.startsWith("/")) {
    return null;
  }

  if (trimmed.startsWith("//")) {
    return null;
  }

  if (/[\u0000-\u001F\u007F]/.test(trimmed)) {
    return null;
  }

  return trimmed;
}

export function resolveRedirectParam(value: string | null | undefined): string {
  return sanitizeNextPath(value) ?? DEFAULT_RETURN_TO;
}

export function buildLoginRedirect(next: string): string {
  return buildRedirectUrl("/login", next);
}

export function buildSetupRedirect(next: string): string {
  return buildRedirectUrl("/setup", next);
}

export function buildRedirectUrl(basePath: string, next: string): string {
  const safeNext = resolveRedirectParam(next);
  const params = new URLSearchParams();
  if (safeNext !== DEFAULT_RETURN_TO) {
    params.set("returnTo", safeNext);
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

export function chooseDestination(
  sessionReturnTo: string | null | undefined,
  queryNext: string | null | undefined,
): string {
  const sessionDestination = sanitizeNextPath(sessionReturnTo);
  if (sessionDestination) {
    return sessionDestination;
  }

  const queryDestination = sanitizeNextPath(queryNext);
  if (queryDestination) {
    return queryDestination;
  }

  return DEFAULT_RETURN_TO;
}
