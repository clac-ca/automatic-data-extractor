const DOCS_ALIAS_PATHS = new Set(["/docs", "/redoc", "/openapi.json"]);
const DOCS_CANONICAL_PREFIXES = ["/api/swagger", "/api/openapi.json", "/api/docs"] as const;

type ClientNavigate = (to: string, options?: { readonly replace?: boolean }) => void;

function getPathname(path: string): string {
  const match = /^[^?#]*/.exec(path);
  const rawPathname = match?.[0] ?? path;
  if (rawPathname.length > 1) {
    return rawPathname.replace(/\/+$/, "");
  }
  return rawPathname;
}

export function isApiDocsPath(path: string): boolean {
  const pathname = getPathname(path);
  if (pathname === "/api") {
    return true;
  }
  if (DOCS_ALIAS_PATHS.has(pathname)) {
    return true;
  }
  return DOCS_CANONICAL_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

interface NavigateToPostAuthPathOptions {
  readonly replace?: boolean;
  readonly documentNavigate?: (nextPath: string, replace: boolean) => void;
}

function defaultDocumentNavigate(nextPath: string, replace: boolean) {
  if (replace) {
    window.location.replace(nextPath);
    return;
  }
  window.location.assign(nextPath);
}

export function navigateToPostAuthPath(
  navigate: ClientNavigate,
  nextPath: string,
  options: NavigateToPostAuthPathOptions = {},
) {
  const replace = options.replace ?? false;
  if (isApiDocsPath(nextPath)) {
    const documentNavigate = options.documentNavigate ?? defaultDocumentNavigate;
    documentNavigate(nextPath, replace);
    return;
  }
  navigate(nextPath, { replace });
}
