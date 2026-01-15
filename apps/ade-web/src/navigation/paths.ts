export function normalizePathname(pathname: string): string {
  let value = pathname || "/";

  const hashIndex = value.indexOf("#");
  if (hashIndex >= 0) {
    value = value.slice(0, hashIndex);
  }

  const queryIndex = value.indexOf("?");
  if (queryIndex >= 0) {
    value = value.slice(0, queryIndex);
  }

  if (!value) {
    return "/";
  }

  if (!value.startsWith("/")) {
    value = `/${value}`;
  }

  const trimmed = value.replace(/\/+$/, "");
  return trimmed || "/";
}
