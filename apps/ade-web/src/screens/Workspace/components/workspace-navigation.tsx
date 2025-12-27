import type { ComponentType, SVGProps } from "react";

import type { WorkspaceProfile } from "@shared/workspaces";

interface IconProps extends SVGProps<SVGSVGElement> {
  readonly title?: string;
}

function createIcon(path: string) {
  return function Icon({ title, ...props }: IconProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden={title ? undefined : true}
        role={title ? "img" : "presentation"}
        {...props}
      >
        {title ? <title>{title}</title> : null}
        <path d={path} />
      </svg>
    );
  };
}

const DocumentsIcon = createIcon(
  "M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM14 3v5a1 1 0 0 0 1 1h5",
);

const RunsIcon = createIcon(
  "M5 6h14M5 12h14M5 18h8M7 4v4M12 10v4M15 16v4",
);

const ConfigureIcon = createIcon(
  "M5 5h5v5H5zM14 5h5v5h-5zM5 14h5v5H5zM16.5 12a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM10 7.5h4M7.5 10v4M15.5 10.5 12 14",
);

const SettingsIcon = createIcon(
  "M5 7h14M5 17h14M9 7a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm10 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm-7-5h7m-9 0H5",
);

type WorkspaceSectionId =
  | "documents"
  | "documents-v2"
  | "documents-v3"
  | "documents-v4"
  | "documents-v5"
  | "documents-v6"
  | "documents-v7"
  | "documents-v8"
  | "documents-v9"
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
    icon: DocumentsIcon,
  },
  {
    id: "documents-v2",
    path: "documents-v2",
    label: "Documents v2",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v3",
    path: "documents-v3",
    label: "Documents v3",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v4",
    path: "documents-v4",
    label: "Documents v4",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v5",
    path: "documents-v5",
    label: "Documents v5",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v6",
    path: "documents-v6",
    label: "Documents v6",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v7",
    path: "documents-v7",
    label: "Documents v7",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v8",
    path: "documents-v8",
    label: "Documents v8",
    icon: DocumentsIcon,
  },
  {
    id: "documents-v9",
    path: "documents-v9",
    label: "Documents v9",
    icon: DocumentsIcon,
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
    icon: SettingsIcon,
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
