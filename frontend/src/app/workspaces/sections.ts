import type { UIMatch } from "react-router-dom";

export type WorkspaceSectionId = "documents" | "config" | "settings";

export interface WorkspaceSectionDescriptor {
  readonly id: WorkspaceSectionId;
  readonly path: string;
  readonly label: string;
  readonly description: string;
  readonly placeholder?: {
    readonly title: string;
    readonly description: string;
    readonly cta?: { readonly href: string; readonly label: string };
  };
}

export interface WorkspaceRouteMeta {
  readonly showContextNav?: boolean;
}

export interface WorkspaceRouteHandle {
  readonly workspaceSectionId?: WorkspaceSectionId;
  readonly meta?: WorkspaceRouteMeta;
}

export const workspaceSections: readonly WorkspaceSectionDescriptor[] = [
  {
    id: "documents",
    path: "documents",
    label: "Documents",
    description: "Uploads, processing status, download history",
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
    description: "Rules, pipelines, and automation",
    placeholder: {
      title: "Configuration",
      description:
        "Define extraction rules, map columns, and manage deployment snapshots. The configuration hub is coming soon.",
      cta: { href: "../documents", label: "View documents" },
    },
  },
  {
    id: "settings",
    path: "settings",
    label: "Workspace Settings",
    description: "Workspace preferences and access controls",
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
