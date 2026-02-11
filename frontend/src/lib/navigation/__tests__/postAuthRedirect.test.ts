import { describe, expect, it, vi } from "vitest";

import { isApiDocsPath, navigateToPostAuthPath } from "@/lib/navigation/postAuthRedirect";

describe("isApiDocsPath", () => {
  it("returns true for canonical docs paths", () => {
    expect(isApiDocsPath("/api")).toBe(true);
    expect(isApiDocsPath("/api/")).toBe(true);
    expect(isApiDocsPath("/api/swagger")).toBe(true);
    expect(isApiDocsPath("/api/swagger?tag=runs")).toBe(true);
    expect(isApiDocsPath("/api/openapi.json")).toBe(true);
    expect(isApiDocsPath("/api/docs")).toBe(true);
  });

  it("returns true for legacy docs aliases", () => {
    expect(isApiDocsPath("/docs")).toBe(true);
    expect(isApiDocsPath("/redoc")).toBe(true);
    expect(isApiDocsPath("/openapi.json")).toBe(true);
  });

  it("returns false for regular app routes and API endpoints", () => {
    expect(isApiDocsPath("/")).toBe(false);
    expect(isApiDocsPath("/workspaces")).toBe(false);
    expect(isApiDocsPath("/api/v1/health")).toBe(false);
  });
});

describe("navigateToPostAuthPath", () => {
  it("uses client navigation for SPA routes", () => {
    const navigate = vi.fn();
    const documentNavigate = vi.fn();

    navigateToPostAuthPath(navigate, "/workspaces", {
      replace: true,
      documentNavigate,
    });

    expect(navigate).toHaveBeenCalledWith("/workspaces", { replace: true });
    expect(documentNavigate).not.toHaveBeenCalled();
  });

  it("uses document navigation for docs routes", () => {
    const navigate = vi.fn();
    const documentNavigate = vi.fn();

    navigateToPostAuthPath(navigate, "/api/swagger?tag=runs", {
      replace: true,
      documentNavigate,
    });

    expect(documentNavigate).toHaveBeenCalledWith("/api/swagger?tag=runs", true);
    expect(navigate).not.toHaveBeenCalled();
  });
});
