import { describe, expect, it } from "vitest";

import { hasRequiredGlobalPermission, hasRequiredWorkspacePermission, parseSettingsRouteContext } from "../utils";

describe("settings routing utils", () => {
  it("parses organization and workspace detail routes", () => {
    expect(parseSettingsRouteContext("/settings/organization/users/user-1")).toMatchObject({
      scope: "organization",
      section: "users.detail",
      entityId: "user-1",
    });

    expect(
      parseSettingsRouteContext(
        "/settings/workspaces/ws-1/access/principals/user/user-1",
      ),
    ).toMatchObject({
      scope: "workspaces",
      section: "principals.detail",
      entityId: "user-1",
      workspaceId: "ws-1",
    });
  });

  it("captures workspace id for section routes", () => {
    expect(parseSettingsRouteContext("/settings/workspaces/ws-2/processing")).toMatchObject({
      scope: "workspaces",
      section: "processing",
      workspaceId: "ws-2",
    });
  });

  it("does not parse create routes as detail entities", () => {
    expect(parseSettingsRouteContext("/settings/organization/users/create")).toMatchObject({
      scope: "organization",
      section: "users.create",
    });

    expect(
      parseSettingsRouteContext("/settings/workspaces/ws-2/access/roles/create"),
    ).toMatchObject({
      scope: "workspaces",
      section: "roles.create",
      workspaceId: "ws-2",
    });
  });

  it("evaluates global permission requirements", () => {
    const permissions = new Set(["users.read_all"]);
    expect(hasRequiredGlobalPermission({ globalAny: ["users.manage_all", "users.read_all"] }, permissions)).toBe(true);
    expect(hasRequiredGlobalPermission({ globalAny: ["roles.manage_all"] }, permissions)).toBe(false);
  });

  it("evaluates workspace permission requirements", () => {
    const workspace = {
      id: "ws-1",
      name: "Workspace",
      slug: "workspace",
      roles: [],
      permissions: ["workspace.members.manage"],
      is_default: false,
      processing_paused: false,
    };

    expect(
      hasRequiredWorkspacePermission({ workspaceAny: ["workspace.members.manage"] }, workspace),
    ).toBe(true);
    expect(
      hasRequiredWorkspacePermission({ workspaceAny: ["workspace.roles.manage"] }, workspace),
    ).toBe(false);
  });
});
