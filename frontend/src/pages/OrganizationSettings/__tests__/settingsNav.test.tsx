import { describe, expect, it, vi } from "vitest";

import {
  buildOrganizationSettingsNav,
  defaultOrganizationSettingsSection,
  getDefaultOrganizationSettingsSection,
  getOrganizationSectionAccessState,
  organizationSettingsSections,
  resolveOrganizationSectionByPath,
} from "../settingsNav";

describe("organization settings nav", () => {
  it("builds grouped navigation links for each section", () => {
    const navGroups = buildOrganizationSettingsNav(() => true);
    const labels = navGroups.flatMap((group) => group.items.map((item) => item.label));
    const links = navGroups.flatMap((group) => group.items.map((item) => item.href));

    expect(links).toEqual([
      "/organization/access/users",
      "/organization/access/groups",
      "/organization/access/roles",
      "/organization/api-keys",
      "/organization/system/sso",
      "/organization/system/safe-mode",
    ]);
    expect(labels).toEqual([
      "Users",
      "Groups",
      "Roles",
      "API Keys",
      "Authentication",
      "Run controls",
    ]);
    expect(defaultOrganizationSettingsSection.path).toBe("access/users");
  });

  it("hides sections when the user has no matching permissions", () => {
    const hasPermission = vi.fn().mockReturnValue(false);
    const nav = buildOrganizationSettingsNav(hasPermission);
    expect(nav).toEqual([]);
    expect(hasPermission).toHaveBeenCalled();
  });

  it("resolves nested paths for deep links", () => {
    const section = resolveOrganizationSectionByPath(["access", "users", "abc-123"]);
    expect(section?.id).toBe("identity.users");
  });

  it("returns the first allowed section as default", () => {
    const section = getDefaultOrganizationSettingsSection((permission) => permission === "api_keys.read_all");
    expect(section.id).toBe("security.apiKeys");
  });

  it("derives section view/edit access from permission sets", () => {
    const usersSection = organizationSettingsSections.find((section) => section.id === "identity.users");
    expect(usersSection).toBeDefined();
    if (!usersSection) {
      return;
    }

    expect(
      getOrganizationSectionAccessState(usersSection, (permission) => permission === "users.read_all"),
    ).toEqual({
      canView: true,
      canEdit: false,
      canAccess: true,
    });

    expect(
      getOrganizationSectionAccessState(usersSection, (permission) => permission === "users.manage_all"),
    ).toEqual({
      canView: true,
      canEdit: true,
      canAccess: true,
    });
  });

  it("exposes all configured sections", () => {
    expect(organizationSettingsSections.map((section) => section.id)).toEqual([
      "identity.users",
      "identity.groups",
      "identity.roles",
      "security.apiKeys",
      "system.sso",
      "system.safeMode",
    ]);
  });
});
