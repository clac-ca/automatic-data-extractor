import type { ComponentType, SVGProps } from "react";

import type { WorkspaceProfile } from "@shared/workspaces";
import { ConfigureIcon, DocumentIcon, GearIcon, RunsIcon } from "@ui/Icons";

type WorkspaceSectionId =
  | "documents"
  | "runs"
  | "config-builder"
  | "settings";

interface WorkspaceSectionDescriptor {
  readonly id: WorkspaceSectionId;
  readonly path: string;
  readonly label: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly matchPrefix?: boolean;
}

const workspaceSections: readonly WorkspaceSectionDescriptor[] = [
  {
    id: "documents",
    path: "documents",
    label: "Documents",
    icon: DocumentIcon,
  },
  {
    id: "runs",
    path: "runs",
    label: "Runs",
    icon: RunsIcon,
  },
  {
    id: "config-builder",
    path: "config-builder",
    label: "Config Builder",
    icon: ConfigureIcon,
  },
  {
    id: "settings",
    path: "settings",
    label: "Workspace Settings",
    icon: GearIcon,
    matchPrefix: true,
  },
] as const;

export const defaultWorkspaceSection = workspaceSections[0];

export interface WorkspaceNavigationItem {
  readonly id: WorkspaceSectionId;
  readonly label: string;
  readonly href: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly matchPrefix?: boolean;
}

export function getWorkspacePrimaryNavigation(workspace: WorkspaceProfile): WorkspaceNavigationItem[] {
  return workspaceSections.map((section) => ({
    id: section.id,
    label: section.label,
    href: `/workspaces/${workspace.id}/${section.path}`,
    icon: section.icon,
    matchPrefix: section.matchPrefix,
  }));
}
