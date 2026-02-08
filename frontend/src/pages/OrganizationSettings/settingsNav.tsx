import type { ReactElement } from "react";
import type { LucideIcon } from "lucide-react";
import { KeyRound, ShieldCheck, ShieldUser, UserRoundCog, Users } from "lucide-react";

import { ApiKeysSettingsPage } from "./pages/ApiKeysSettingsPage";
import { RolesSettingsPage } from "./pages/RolesSettingsPage";
import { SystemSafeModeSettingsPage } from "./pages/SystemSafeModeSettingsPage";
import { SystemSsoSettingsPage } from "./pages/SystemSsoSettingsPage";
import { UsersSettingsPage } from "./pages/UsersSettingsPage";

export type OrganizationSettingsRouteId =
  | "identity.users"
  | "identity.roles"
  | "security.apiKeys"
  | "system.sso"
  | "system.safeMode";

export type OrganizationSettingsGroupId = "identity" | "security" | "system";

export type OrganizationSettingsSection = {
  readonly id: OrganizationSettingsRouteId;
  readonly group: OrganizationSettingsGroupId;
  readonly groupOrder: number;
  readonly label: string;
  readonly shortLabel: string;
  readonly description: string;
  readonly path: string;
  readonly icon: LucideIcon;
  readonly required?: { readonly view?: string[]; readonly edit?: string[] };
  readonly element: ReactElement;
};

export interface OrganizationSettingsNavItem {
  readonly id: OrganizationSettingsRouteId;
  readonly group: OrganizationSettingsGroupId;
  readonly label: string;
  readonly shortLabel: string;
  readonly description: string;
  readonly icon: LucideIcon;
  readonly href: string;
  readonly canView: boolean;
  readonly canEdit: boolean;
  readonly disabled?: boolean;
}

export interface OrganizationSettingsNavGroup {
  readonly id: OrganizationSettingsGroupId;
  readonly label: string;
  readonly items: OrganizationSettingsNavItem[];
}

const GROUP_LABELS: Record<OrganizationSettingsGroupId, string> = {
  identity: "Identity",
  security: "Security",
  system: "System",
};

export const organizationSettingsSections: OrganizationSettingsSection[] = [
  {
    id: "identity.users",
    group: "identity",
    groupOrder: 1,
    label: "Users",
    shortLabel: "Users",
    description: "Manage user accounts and access status.",
    path: "users",
    icon: Users,
    required: { view: ["users.read_all", "users.manage_all"], edit: ["users.manage_all"] },
    element: <UsersSettingsPage />,
  },
  {
    id: "identity.roles",
    group: "identity",
    groupOrder: 1,
    label: "Roles",
    shortLabel: "Roles",
    description: "Define global roles and permission bundles.",
    path: "roles",
    icon: ShieldUser,
    required: { view: ["roles.read_all", "roles.manage_all"], edit: ["roles.manage_all"] },
    element: <RolesSettingsPage />,
  },
  {
    id: "security.apiKeys",
    group: "security",
    groupOrder: 2,
    label: "API Keys",
    shortLabel: "API Keys",
    description: "Audit and manage API keys across the organization.",
    path: "api-keys",
    icon: KeyRound,
    required: { view: ["api_keys.read_all", "api_keys.manage_all"], edit: ["api_keys.manage_all"] },
    element: <ApiKeysSettingsPage />,
  },
  {
    id: "system.sso",
    group: "system",
    groupOrder: 3,
    label: "SSO",
    shortLabel: "SSO",
    description: "Configure identity providers and SSO behavior.",
    path: "system/sso",
    icon: UserRoundCog,
    required: {
      view: ["system.settings.read", "system.settings.manage"],
      edit: ["system.settings.manage"],
    },
    element: <SystemSsoSettingsPage />,
  },
  {
    id: "system.safeMode",
    group: "system",
    groupOrder: 3,
    label: "Safe mode",
    shortLabel: "Safe mode",
    description: "Control maintenance mode for run execution.",
    path: "system/safe-mode",
    icon: ShieldCheck,
    required: {
      view: ["system.settings.read", "system.settings.manage"],
      edit: ["system.settings.manage"],
    },
    element: <SystemSafeModeSettingsPage />,
  },
] as const;

export const defaultOrganizationSettingsSection = organizationSettingsSections[0];

export interface OrganizationSectionAccessState {
  readonly canView: boolean;
  readonly canEdit: boolean;
  readonly canAccess: boolean;
}

export function resolveOrganizationSectionByPath(pathSegments: readonly string[]): OrganizationSettingsSection | undefined {
  const normalized = pathSegments.join("/");
  return organizationSettingsSections.find(
    (section) => normalized === section.path || normalized.startsWith(`${section.path}/`),
  );
}

export function getOrganizationSectionAccessState(
  section: OrganizationSettingsSection,
  hasPermission: (permission: string) => boolean,
): OrganizationSectionAccessState {
  const viewPerms = section.required?.view ?? [];
  const editPerms = section.required?.edit ?? [];
  if (viewPerms.length === 0 && editPerms.length === 0) {
    return { canView: true, canEdit: true, canAccess: true };
  }

  const canView = viewPerms.length === 0 ? false : viewPerms.some((perm) => hasPermission(perm));
  const canEdit = editPerms.length === 0 ? false : editPerms.some((perm) => hasPermission(perm));
  return {
    canView,
    canEdit,
    canAccess: canView || canEdit,
  };
}

export function getDefaultOrganizationSettingsSection(
  hasPermission: (permission: string) => boolean,
): OrganizationSettingsSection {
  const firstAllowed = organizationSettingsSections.find(
    (section) => getOrganizationSectionAccessState(section, hasPermission).canAccess,
  );

  return firstAllowed ?? defaultOrganizationSettingsSection;
}

export function buildOrganizationSettingsNav(
  hasPermission: (permission: string) => boolean,
): OrganizationSettingsNavGroup[] {
  const items = organizationSettingsSections
    .filter((section) => getOrganizationSectionAccessState(section, hasPermission).canAccess)
    .map((section) => {
      const accessState = getOrganizationSectionAccessState(section, hasPermission);
      return {
        id: section.id,
        group: section.group,
        label: section.label,
        shortLabel: section.shortLabel,
        description: section.description,
        icon: section.icon,
        href: `/organization/${section.path}`,
        canView: accessState.canView,
        canEdit: accessState.canEdit,
        disabled: !accessState.canAccess,
      };
    });

  return Object.values(
    items.reduce<Record<OrganizationSettingsGroupId, OrganizationSettingsNavGroup>>((groups, item) => {
      const existing = groups[item.group];
      const next: OrganizationSettingsNavGroup = existing
        ? { ...existing, items: [...existing.items, item] }
        : { id: item.group, label: GROUP_LABELS[item.group], items: [item] };
      groups[item.group] = next;
      return groups;
    }, {} as Record<OrganizationSettingsGroupId, OrganizationSettingsNavGroup>),
  ).sort((left, right) => {
    const leftOrder = organizationSettingsSections.find((section) => section.group === left.id)?.groupOrder ?? 999;
    const rightOrder = organizationSettingsSections.find((section) => section.group === right.id)?.groupOrder ?? 999;
    return leftOrder - rightOrder;
  });
}
