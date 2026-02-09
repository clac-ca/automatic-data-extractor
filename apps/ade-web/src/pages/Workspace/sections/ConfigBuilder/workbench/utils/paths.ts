export function normalizeWorkbenchPath(path: string) {
  return (path || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/\/+/g, "/")
    .replace(/^\/+/, "")
    .replace(/\/+$/, "");
}

export function joinWorkbenchPath(folderPath: string, relativePath: string) {
  const base = normalizeWorkbenchPath(folderPath);
  const suffix = normalizeWorkbenchPath(relativePath);
  if (!base) {
    return suffix;
  }
  if (!suffix) {
    return base;
  }
  return `${base}/${suffix}`.replace(/\/+/g, "/");
}

export function isSafeWorkbenchPath(path: string) {
  const normalized = normalizeWorkbenchPath(path);
  if (!normalized) {
    return false;
  }
  const parts = normalized.split("/");
  return parts.every((part) => part.length > 0 && part !== "." && part !== "..");
}

export function isAssetsWorkbenchPath(path: string) {
  const normalized = normalizeWorkbenchPath(path);
  return normalized === "assets" || normalized.startsWith("assets/");
}

