import { describe, expect, it } from "vitest";

import { settingsPaths } from "../contracts";

describe("settings route contract", () => {
  it("uses create routes for organization resources", () => {
    expect(settingsPaths.organization.usersCreate).toBe("/settings/organization/users/create");
    expect(settingsPaths.organization.groupsCreate).toBe("/settings/organization/groups/create");
    expect(settingsPaths.organization.rolesCreate).toBe("/settings/organization/roles/create");
  });

  it("uses create routes for workspace access resources", () => {
    expect(settingsPaths.workspaces.principalsCreate("ws-1")).toBe(
      "/settings/workspaces/ws-1/access/principals/create",
    );
    expect(settingsPaths.workspaces.rolesCreate("ws-1")).toBe(
      "/settings/workspaces/ws-1/access/roles/create",
    );
    expect(settingsPaths.workspaces.invitationsCreate("ws-1")).toBe(
      "/settings/workspaces/ws-1/access/invitations/create",
    );
  });

  it("encodes dynamic ids for shareable deep links", () => {
    expect(settingsPaths.organization.userDetail("user/a")).toBe(
      "/settings/organization/users/user%2Fa",
    );
    expect(settingsPaths.workspaces.roleDetail("ws:a", "role/a")).toBe(
      "/settings/workspaces/ws%3Aa/access/roles/role%2Fa",
    );
  });
});
