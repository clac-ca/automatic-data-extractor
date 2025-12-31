import { describe, expect, it, vi } from "vitest";

import {
  buildSettingsNav,
  defaultSettingsSection,
  resolveSectionByPath,
  workspaceSettingsSections,
} from "../settingsNav";

describe("settingsNav", () => {
  it("builds grouped navigation links for each section", () => {
    const navGroups = buildSettingsNav("ws-123", () => true);
    const links = navGroups.flatMap((group) => group.items.map((item) => item.href));
    expect(links).toEqual([
      "/workspaces/ws-123/settings/general",
      "/workspaces/ws-123/settings/processing",
      "/workspaces/ws-123/settings/preferences/appearance",
      "/workspaces/ws-123/settings/access/members",
      "/workspaces/ws-123/settings/access/roles",
      "/workspaces/ws-123/settings/lifecycle/danger",
    ]);
    expect(defaultSettingsSection.path).toBe("general");
  });

  it("disables sections that require permissions the user lacks", () => {
    const hasPermission = vi.fn().mockReturnValue(false);
    const nav = buildSettingsNav("ws-1", hasPermission);
    const danger = nav.flatMap((group) => group.items).find((item) => item.id === "lifecycle.danger");
    expect(danger?.disabled).toBe(true);
    expect(hasPermission).toHaveBeenCalledWith("workspace.settings.manage");
  });

  it("enables danger when a permissive scope is present", () => {
    const nav = buildSettingsNav("ws-9", (key) => key === "workspace.settings.manage");
    const danger = nav.flatMap((group) => group.items).find((item) => item.id === "lifecycle.danger");
    expect(danger?.disabled).toBe(false);
  });

  it("exposes all configured sections in the registry", () => {
    expect(workspaceSettingsSections.map((section) => section.id)).toEqual([
      "workspace.general",
      "workspace.processing",
      "preferences.appearance",
      "access.members",
      "access.roles",
      "lifecycle.danger",
    ]);
  });

  it("resolves nested section paths for deep links", () => {
    const section = resolveSectionByPath(["access", "members", "user-123"]);
    expect(section?.id).toBe("access.members");
  });
});
