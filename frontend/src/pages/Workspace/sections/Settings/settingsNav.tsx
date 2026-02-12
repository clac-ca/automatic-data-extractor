import type { ReactElement } from "react";

import { DangerSettingsPage } from "./pages/DangerSettingsPage";
import { GeneralSettingsPage } from "./pages/GeneralSettingsPage";
import { InvitationsSettingsPage } from "./pages/InvitationsSettingsPage";
import { MembersSettingsPage } from "./pages/MembersSettingsPage";
import { ProcessingSettingsPage } from "./pages/ProcessingSettingsPage";
import { RolesSettingsPage } from "./pages/RolesSettingsPage";

export type WorkspaceSettingsRouteId =
  | "workspace.general"
  | "workspace.processing"
  | "access.principals"
  | "access.roles"
  | "access.invitations"
  | "lifecycle.danger";

export type SettingsGroupId = "workspace" | "access" | "lifecycle";

export type SettingsSection = {
  readonly id: WorkspaceSettingsRouteId;
  readonly group: SettingsGroupId;
  readonly label: string;
  readonly description: string;
  readonly path: string;
  readonly required?: { readonly view?: string[]; readonly edit?: string[] };
  readonly tone?: "default" | "danger";
  readonly element: ReactElement;
};

export interface WorkspaceSettingsNavItem {
  readonly id: WorkspaceSettingsRouteId;
  readonly label: string;
  readonly description: string;
  readonly href: string;
  readonly disabled?: boolean;
  readonly tone?: "default" | "danger";
}

export interface WorkspaceSettingsNavGroup {
  readonly id: SettingsGroupId;
  readonly label: string;
  readonly items: WorkspaceSettingsNavItem[];
}

const GROUP_LABELS: Record<SettingsGroupId, string> = {
  workspace: "Workspace",
  access: "Access",
  lifecycle: "Lifecycle",
};

export const workspaceSettingsSections: SettingsSection[] = [
  {
    id: "workspace.general",
    group: "workspace",
    label: "General",
    description: "Workspace name, slug, and defaults.",
    path: "general",
    element: <GeneralSettingsPage />,
  },
  {
    id: "workspace.processing",
    group: "workspace",
    label: "Processing",
    description: "Pause or resume automatic processing.",
    path: "processing",
    required: { view: ["workspace.settings.manage"], edit: ["workspace.settings.manage"] },
    element: <ProcessingSettingsPage />,
  },
  {
    id: "access.principals",
    group: "access",
    label: "Principals",
    description: "Manage user and group access.",
    path: "access/principals",
    required: { view: ["workspace.members.read"], edit: ["workspace.members.manage"] },
    element: <MembersSettingsPage />,
  },
  {
    id: "access.roles",
    group: "access",
    label: "Roles",
    description: "Workspace-scoped roles and permissions.",
    path: "access/roles",
    required: { view: ["workspace.roles.read"], edit: ["workspace.roles.manage"] },
    element: <RolesSettingsPage />,
  },
  {
    id: "access.invitations",
    group: "access",
    label: "Invitations",
    description: "Track and manage workspace invitations.",
    path: "access/invitations",
    required: {
      view: ["workspace.invitations.read", "workspace.invitations.manage"],
      edit: ["workspace.invitations.manage"],
    },
    element: <InvitationsSettingsPage />,
  },
  {
    id: "lifecycle.danger",
    group: "lifecycle",
    label: "Danger zone",
    description: "Deletion and operational safeguards.",
    path: "lifecycle/danger",
    tone: "danger",
    required: { view: ["workspace.settings.manage", "workspace.delete"], edit: ["workspace.delete"] },
    element: <DangerSettingsPage />,
  },
] as const;

export const defaultSettingsSection = workspaceSettingsSections[0];

export function isSettingsPath(value: string | undefined): boolean {
  if (!value) return false;
  return workspaceSettingsSections.some((section) => value.startsWith(section.path));
}

export function resolveSectionByPath(pathSegments: readonly string[]): SettingsSection | undefined {
  const normalized = pathSegments.join("/");
  return workspaceSettingsSections.find(
    (section) => normalized === section.path || normalized.startsWith(`${section.path}/`),
  );
}

export function buildSettingsNav(
  workspaceId: string,
  hasPermission: (permission: string) => boolean,
): WorkspaceSettingsNavGroup[] {
  const items = workspaceSettingsSections.map((section) => {
    const canView = section.required?.view ? section.required.view.some((perm) => hasPermission(perm)) : true;
    const canEdit = section.required?.edit ? section.required.edit.some((perm) => hasPermission(perm)) : true;
    return {
      id: section.id,
      label: section.label,
      description: section.description,
      href: `/workspaces/${workspaceId}/settings/${section.path}`,
      disabled: !(canView || canEdit),
      tone: section.tone ?? "default",
    };
  });

  return Object.values(
    items.reduce<Record<SettingsGroupId, WorkspaceSettingsNavGroup>>((groups, item) => {
      const section = workspaceSettingsSections.find((entry) => entry.id === item.id);
      if (!section) {
        return groups;
      }
      const existing = groups[section.group];
      const next: WorkspaceSettingsNavGroup = existing
        ? { ...existing, items: [...existing.items, item] }
        : { id: section.group, label: GROUP_LABELS[section.group], items: [item] };
      groups[section.group] = next;
      return groups;
    }, {} as Record<SettingsGroupId, WorkspaceSettingsNavGroup>),
  );
}
