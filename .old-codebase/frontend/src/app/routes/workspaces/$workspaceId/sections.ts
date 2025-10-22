import type { ComponentType, SVGProps } from "react";

import type { WorkspaceProfile } from "@shared/types/workspaces";
import { ConfigureIcon, DocumentsIcon, SettingsIcon } from "./icons";

export type WorkspaceSectionId = "documents" | "configurations" | "settings";

interface WorkspaceSectionDescriptor {
  readonly id: WorkspaceSectionId;
  readonly path: string;
  readonly label: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
}

const workspaceSections: readonly WorkspaceSectionDescriptor[] = [
  {
    id: "documents",
    path: "documents",
    label: "Documents",
    icon: DocumentsIcon,
  },
  {
    id: "configurations",
    path: "configurations",
    label: "Configurations",
    icon: ConfigureIcon,
  },
  {
    id: "settings",
    path: "settings",
    label: "Workspace Settings",
    icon: SettingsIcon,
  },
] as const;

export const defaultWorkspaceSection = workspaceSections[0];

export function getWorkspacePrimaryNavigation(workspace: WorkspaceProfile) {
  return workspaceSections.map((section) => ({
    id: section.id,
    label: section.label,
    href: `/workspaces/${workspace.id}/${section.path}`,
    icon: section.icon,
  }));
}
