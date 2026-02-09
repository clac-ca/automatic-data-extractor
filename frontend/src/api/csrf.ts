const DEFAULT_CSRF_COOKIE_NAMES = ["ade_csrf", "backend_app_csrf"];

function getConfiguredCookieNames(): readonly string[] {
  const configured =
    import.meta.env.VITE_SESSION_CSRF_COOKIE ?? import.meta.env.VITE_SESSION_CSRF_COOKIE_NAME;
  if (typeof configured === "string") {
    const trimmed = configured.trim();
    if (trimmed.length > 0) {
      return [trimmed];
    }
  }
  return DEFAULT_CSRF_COOKIE_NAMES;
}

function readCookieMap(): Map<string, string> | null {
  if (typeof document === "undefined") {
    return null;
  }
  const rawCookies = document.cookie;
  if (!rawCookies) {
    return null;
  }

  const map = new Map<string, string>();
  const entries = rawCookies.split(";");
  for (const entry of entries) {
    const [rawName, ...valueParts] = entry.trim().split("=");
    if (!rawName) {
      continue;
    }
    map.set(rawName, decodeURIComponent(valueParts.join("=")));
  }
  return map;
}

export function readCsrfToken(): string | null {
  const cookies = readCookieMap();
  if (!cookies) {
    return null;
  }

  for (const name of getConfiguredCookieNames()) {
    const token = cookies.get(name);
    if (token) {
      return token;
    }
  }

  return null;
}

