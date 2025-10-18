import type { ComponentType, SVGProps } from "react";
import type { UIMatch } from "react-router-dom";

import type { WorkspaceProfile } from "../../shared/types/workspaces";
import { ConfigureIcon, DocumentsIcon, SettingsIcon } from "./icons";

export type WorkspaceSectionId = "documents" | "config" | "settings";

export interface WorkspaceRouteMeta {
  readonly showContextNav?: boolean;
}

export type WorkspaceSecondaryNavigationConfig =
  | {
      readonly type: "static";
      readonly items: readonly WorkspaceSecondaryNavDefinition[];
      readonly emptyLabel?: string;
    }
  | {
      readonly type: "dynamic";
      readonly emptyLabel?: string;
    };

export interface WorkspaceSectionDescriptor {
  readonly id: WorkspaceSectionId;
  readonly path: string;
  readonly label: string;
  readonly description: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly placeholder?: {
    readonly title: string;
    readonly description: string;
    readonly cta?: { readonly href: string; readonly label: string };
  };
  readonly navigation?: WorkspaceSecondaryNavigationConfig;
  readonly meta?: WorkspaceRouteMeta;
}

export interface WorkspaceRouteHandle {
  readonly workspaceSectionId?: WorkspaceSectionId;
  readonly meta?: WorkspaceRouteMeta;
}

export interface WorkspacePrimaryNavItem {
  readonly id: WorkspaceSectionId;
  readonly label: string;
  readonly description: string;
  readonly href: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
}

export interface WorkspaceSecondaryNavItem {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly badge?: string;
}

export interface WorkspaceSecondaryNavigation {
  readonly status: "ready" | "loading" | "empty";
  readonly items: WorkspaceSecondaryNavItem[];
  readonly emptyLabel: string;
}

type WorkspaceSecondaryNavDefinition =
  | WorkspaceSecondaryNavItem
  | ((workspaceId: string) => WorkspaceSecondaryNavItem);

export const workspaceSections: readonly WorkspaceSectionDescriptor[] = [
  {
    id: "documents",
    path: "documents",
    label: "Documents",
    description: "Uploads, processing status, download history",
    icon: DocumentsIcon,
    placeholder: {
      title: "Documents",
      description:
        "Upload spreadsheets or PDFs, monitor extraction progress, and collaborate with teammates in real time.",
      cta: { href: "../documents", label: "Refresh" },
    },
  },
  {
    id: "config",
    path: "config",
    label: "Configuration",
    description: "Author extraction columns, scripts, and deployment snapshots",
    icon: ConfigureIcon,
    meta: { showContextNav: true },
    navigation: {
      type: "static",
      items: [
        (workspaceId) => ({
          id: "config-columns",
          label: "Columns",
          href: `/workspaces/${workspaceId}/config?view=columns`,
        }),
        (workspaceId) => ({
          id: "config-scripts",
          label: "Scripts",
          href: `/workspaces/${workspaceId}/config?view=scripts`,
        }),
      ],
      emptyLabel: "Define columns and scripts to configure extraction logic.",
    },
    placeholder: {
      title: "Configuration",
      description:
        "Define columns, bind scripts, and activate configurations to control how ADE processes documents.",
      cta: { href: "../config?view=columns", label: "Open configuration" },
    },
  },
  {
    id: "settings",
    path: "settings",
    label: "Workspace Settings",
    description: "Workspace preferences and access controls",
    icon: SettingsIcon,
    meta: { showContextNav: true },
    navigation: {
      type: "static",
      items: [
        (workspaceId) => ({
          id: "settings-general",
          label: "General",
          href: `/workspaces/${workspaceId}/settings?view=general`,
        }),
        (workspaceId) => ({
          id: "settings-members",
          label: "Members",
          href: `/workspaces/${workspaceId}/settings?view=members`,
        }),
        (workspaceId) => ({
          id: "settings-roles",
          label: "Roles",
          href: `/workspaces/${workspaceId}/settings?view=roles`,
        }),
      ],
      emptyLabel: "Workspace settings will appear here soon.",
    },
    placeholder: {
      title: "Workspace settings",
      description:
        "Adjust workspace preferences, integrations, and retention rules. The full settings experience will appear after the authentication revamp ships.",
    },
  },
] as const;

export const defaultWorkspaceSection: WorkspaceSectionDescriptor = workspaceSections[0];

const sectionsById = new Map(workspaceSections.map((section) => [section.id, section] as const));

export function getWorkspaceSection(sectionId: WorkspaceSectionId): WorkspaceSectionDescriptor {
  const match = sectionsById.get(sectionId);
  if (!match) {
    throw new Error(`Unknown workspace section: ${sectionId}`);
  }
  return match;
}

export function buildWorkspaceSectionPath(workspaceId: string, sectionId: WorkspaceSectionId) {
  const section = getWorkspaceSection(sectionId);
  return `/workspaces/${workspaceId}/${section.path}`;
}

export function matchWorkspaceSection(matches: readonly UIMatch[]): WorkspaceSectionDescriptor {
  for (let index = matches.length - 1; index >= 0; index -= 1) {
    const handle = matches[index].handle as WorkspaceRouteHandle | undefined;
    if (handle?.workspaceSectionId) {
      return getWorkspaceSection(handle.workspaceSectionId);
    }
  }
  return defaultWorkspaceSection;
}

export function matchWorkspaceSectionMeta(matches: readonly UIMatch[]): WorkspaceRouteMeta {
  for (let index = matches.length - 1; index >= 0; index -= 1) {
    const handle = matches[index].handle as WorkspaceRouteHandle | undefined;
    if (handle?.workspaceSectionId) {
      return handle.meta ?? {};
    }
  }
  return {};
}

export const workspacePlaceholderSections = new Map(
  workspaceSections
    .map((section) => [section.id, section.placeholder])
    .filter(([, placeholder]) => Boolean(placeholder)) as Array<
      [string, WorkspaceSectionDescriptor["placeholder"]]
    >,
);

export function getWorkspacePlaceholder(sectionId: string) {
  return (
    workspacePlaceholderSections.get(sectionId) ?? {
      title: "Workspace surface coming soon",
      description:
        "We haven’t wired this route yet. Once the backend API is stable we’ll light up the UI here.",
      cta: { href: "/workspaces", label: "View all workspaces" },
    }
  );
}

export function getWorkspacePrimaryNavigation(workspace: WorkspaceProfile): WorkspacePrimaryNavItem[] {
  return workspaceSections.map((section) => ({
    id: section.id,
    label: section.label,
    description: section.description,
    href: buildWorkspaceSectionPath(workspace.id, section.id),
    icon: section.icon,
  }));
}

export function getWorkspaceSecondaryNavigation(
  workspaceId: string,
  section: WorkspaceSectionDescriptor,
): WorkspaceSecondaryNavigation {
  const config = section.navigation;
  const fallbackEmptyLabel = `No ${section.label.toLowerCase()} views yet.`;

  if (!config) {
    return { status: "empty", items: [], emptyLabel: fallbackEmptyLabel };
  }

  if (config.type === "dynamic") {
    return { status: "loading", items: [], emptyLabel: config.emptyLabel ?? fallbackEmptyLabel };
  }

  const items = config.items.map((definition) =>
    typeof definition === "function" ? definition(workspaceId) : definition,
  );
  if (items.length === 0) {
    return { status: "empty", items: [], emptyLabel: config.emptyLabel ?? fallbackEmptyLabel };
  }
  return { status: "ready", items, emptyLabel: config.emptyLabel ?? fallbackEmptyLabel };
}
