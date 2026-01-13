import { describe, expect, it } from "vitest";

import {
  DEFAULT_RETURN_TO,
  buildLoginRedirect,
  buildSetupRedirect,
  buildRedirectUrl,
  chooseDestination,
  isPublicPath,
  joinPath,
  type LocationLike,
  normalizeNextFromLocation,
  resolveRedirectParam,
  sanitizeNextPath,
} from "../authNavigation";

function mockLocation(input: Partial<LocationLike> = {}): LocationLike {
  return {
    pathname: input.pathname ?? "/workspaces",
    search: input.search ?? "",
    hash: input.hash ?? "",
  };
}

describe("authNavigation utils", () => {
  it("detects public paths", () => {
    expect(isPublicPath("/")).toBe(true);
    expect(isPublicPath("/login")).toBe(true);
    expect(isPublicPath("/setup")).toBe(true);
    expect(isPublicPath("/logout")).toBe(true);
    expect(isPublicPath("/workspaces")).toBe(false);
  });

  it("joins location parts", () => {
    const location = mockLocation({ pathname: "/workspaces", search: "?view=list", hash: "#top" });
    expect(joinPath(location)).toBe("/workspaces?view=list#top");
  });

  it("normalizes next path from location", () => {
    expect(normalizeNextFromLocation(mockLocation({ pathname: "/" }))).toBe(DEFAULT_RETURN_TO);
    expect(normalizeNextFromLocation(mockLocation({ pathname: "/workspaces/123" }))).toBe(
      "/workspaces/123",
    );
  });

  it("sanitizes next paths", () => {
    expect(sanitizeNextPath(null)).toBeNull();
    expect(sanitizeNextPath("")).toBeNull();
    expect(sanitizeNextPath("relative")).toBeNull();
    expect(sanitizeNextPath("//evil.com")).toBeNull();
    expect(sanitizeNextPath("/login")).toBe("/login");
    expect(sanitizeNextPath("/workspaces/123")).toBe("/workspaces/123");
    expect(sanitizeNextPath("/")).toBe("/");
  });

  it("chooses destination with precedence", () => {
    expect(chooseDestination("/workspaces/abc", "/workspaces/def")).toBe("/workspaces/abc");
    expect(chooseDestination(null, "/workspaces/def")).toBe("/workspaces/def");
    expect(chooseDestination(null, "/login")).toBe("/login");
    expect(chooseDestination(null, null)).toBe(DEFAULT_RETURN_TO);
  });

  it("builds login redirect URLs", () => {
    expect(buildLoginRedirect("/workspaces")).toBe("/login?returnTo=%2Fworkspaces");
    expect(buildLoginRedirect("/workspaces/123")).toBe("/login?returnTo=%2Fworkspaces%2F123");
    expect(buildLoginRedirect("/workspaces/123?tab=settings")).toBe(
      "/login?returnTo=%2Fworkspaces%2F123%3Ftab%3Dsettings",
    );
    expect(buildLoginRedirect("//evil")).toBe("/login");
  });

  it("builds setup redirect URLs", () => {
    expect(buildSetupRedirect("/workspaces")).toBe("/setup?returnTo=%2Fworkspaces");
    expect(buildSetupRedirect("/workspaces/xyz")).toBe("/setup?returnTo=%2Fworkspaces%2Fxyz");
    expect(buildSetupRedirect("/workspaces/xyz?tab=settings")).toBe(
      "/setup?returnTo=%2Fworkspaces%2Fxyz%3Ftab%3Dsettings",
    );
    expect(buildSetupRedirect("//evil")).toBe("/setup");
  });

  it("builds redirect URLs for arbitrary paths", () => {
    expect(buildRedirectUrl("/login", "/workspaces/team")).toBe(
      "/login?returnTo=%2Fworkspaces%2Fteam",
    );
    expect(buildRedirectUrl("/login", DEFAULT_RETURN_TO)).toBe("/login");
  });

  it("resolves redirect parameters", () => {
    expect(resolveRedirectParam("/workspaces/alpha")).toBe("/workspaces/alpha");
    expect(resolveRedirectParam("//bad")).toBe(DEFAULT_RETURN_TO);
    expect(resolveRedirectParam("")).toBe(DEFAULT_RETURN_TO);
    expect(resolveRedirectParam(null)).toBe(DEFAULT_RETURN_TO);
  });
});
