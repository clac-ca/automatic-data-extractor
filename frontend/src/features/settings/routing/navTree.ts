import {
  Building2,
  Home,
  KeyRound,
  Mail,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  ShieldUser,
  Users,
  UserRoundCog,
  type LucideIcon,
} from "lucide-react";

import type { SettingsNavNode } from "./contracts";
import { settingsPaths } from "./contracts";

export interface SettingsRailItem extends SettingsNavNode {
  readonly icon: LucideIcon;
  readonly tone?: "default" | "danger";
}

export interface SettingsRailGroup {
  readonly id: string;
  readonly label: string;
  readonly items: readonly SettingsRailItem[];
}

export const settingsRail: readonly SettingsRailGroup[] = [
  {
    id: "home",
    label: "Home",
    items: [
      {
        id: "home.overview",
        label: "Overview",
        path: settingsPaths.home,
        scope: "home",
        icon: Home,
      },
    ],
  },
  {
    id: "organization",
    label: "Organization",
    items: [
      {
        id: "organization.users",
        label: "Users",
        path: settingsPaths.organization.users,
        scope: "organization",
        icon: Users,
        requiredPermissions: { globalAny: ["users.read_all", "users.manage_all"] },
      },
      {
        id: "organization.groups",
        label: "Groups",
        path: settingsPaths.organization.groups,
        scope: "organization",
        icon: Users,
        requiredPermissions: { globalAny: ["groups.read_all", "groups.manage_all"] },
      },
      {
        id: "organization.roles",
        label: "Roles",
        path: settingsPaths.organization.roles,
        scope: "organization",
        icon: ShieldUser,
        requiredPermissions: { globalAny: ["roles.read_all", "roles.manage_all"] },
      },
      {
        id: "organization.apiKeys",
        label: "API keys",
        path: settingsPaths.organization.apiKeys,
        scope: "organization",
        icon: KeyRound,
        requiredPermissions: { globalAny: ["api_keys.read_all", "api_keys.manage_all"] },
      },
      {
        id: "organization.authentication",
        label: "Authentication",
        path: settingsPaths.organization.authentication,
        scope: "organization",
        icon: UserRoundCog,
        requiredPermissions: { globalAny: ["system.settings.read", "system.settings.manage"] },
      },
      {
        id: "organization.runControls",
        label: "Run controls",
        path: settingsPaths.organization.runControls,
        scope: "organization",
        icon: ShieldCheck,
        requiredPermissions: { globalAny: ["system.settings.read", "system.settings.manage"] },
      },
    ],
  },
  {
    id: "workspaces",
    label: "Workspaces",
    items: [
      {
        id: "workspaces.list",
        label: "Workspaces",
        path: settingsPaths.workspaces.list,
        scope: "workspaces",
        icon: Building2,
      },
      {
        id: "workspaces.general",
        label: "General",
        path: "/settings/workspaces/:workspaceId/general",
        scope: "workspaces",
        icon: Settings2,
      },
      {
        id: "workspaces.processing",
        label: "Processing",
        path: "/settings/workspaces/:workspaceId/processing",
        scope: "workspaces",
        icon: ShieldCheck,
        requiredPermissions: { workspaceAny: ["workspace.settings.manage"] },
      },
      {
        id: "workspaces.principals",
        label: "Principals",
        path: "/settings/workspaces/:workspaceId/access/principals",
        scope: "workspaces",
        icon: Users,
        requiredPermissions: {
          workspaceAny: ["workspace.members.read", "workspace.members.manage"],
        },
      },
      {
        id: "workspaces.roles",
        label: "Roles",
        path: "/settings/workspaces/:workspaceId/access/roles",
        scope: "workspaces",
        icon: ShieldUser,
        requiredPermissions: {
          workspaceAny: ["workspace.roles.read", "workspace.roles.manage"],
        },
      },
      {
        id: "workspaces.invitations",
        label: "Invitations",
        path: "/settings/workspaces/:workspaceId/access/invitations",
        scope: "workspaces",
        icon: Mail,
        requiredPermissions: {
          workspaceAny: ["workspace.invitations.read", "workspace.invitations.manage"],
        },
      },
      {
        id: "workspaces.danger",
        label: "Danger",
        path: "/settings/workspaces/:workspaceId/lifecycle/danger",
        scope: "workspaces",
        icon: ShieldAlert,
        tone: "danger",
        requiredPermissions: { workspaceAny: ["workspace.delete", "workspace.settings.manage"] },
      },
    ],
  },
] as const;
