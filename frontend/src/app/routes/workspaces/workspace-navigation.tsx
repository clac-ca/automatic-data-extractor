import type { ComponentType, SVGProps } from "react";

import type { WorkspaceProfile } from "./workspaces-api";

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

export const DocumentsIcon = createIcon(
  "M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM14 3v5a1 1 0 0 0 1 1h5",
);

export const ConfigureIcon = createIcon(
  "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a1 1 0 0 0 .1-.4 1 1 0 0 0-.1-.4l2-1.6a1 1 0 0 0 .2-1.3l-1.9-3.2a1 1 0 0 0-1.2-.4l-2.3.9a7 7 0 0 0-1.3-.8l-.4-2.4A1 1 0 0 0 13.5 1h-3a1 1 0 0 0-1 .9l-.4 2.4a7 7 0 0 0-1.3.8l-2.3-.9a1 1 0 0 0-1.2.4L2.4 7.8a1 1 0 0 0 .2 1.3l2 1.5a3 3 0 0 0 0 .8l-2 1.6a1 1 0 0 0-.2 1.3l1.9 3.2a1 1 0 0 0 1.2.4l2.3-.9a7 7 0 0 0 1.3.8l.4 2.4a1 1 0 0 0 1 .9h3a1 1 0 0 0 1-.9l.4-2.4a7 7 0 0 0 1.3-.8l2.3.9a1 1 0 0 0 1.2-.4l1.9-3.1a1 1 0 0 0-.2-1.3l-2-1.7Z",
);

export const SettingsIcon = createIcon(
  "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a1 1 0 0 0 .1-.4 1 1 0 0 0-.1-.4l2-1.6a1 1 0 0 0 .2-1.3l-1.9-3.2a1 1 0 0 0-1.2-.4l-2.3.9a7 7 0 0 0-1.3-.8l-.4-2.4A1 1 0 0 0 13.5 1h-3a1 1 0 0 0-1 .9l-.4 2.4a7 7 0 0 0-1.3.8l-2.3-.9a1 1 0 0 0-1.2.4L2.4 7.8a1 1 0 0 0 .2 1.3l2 1.5a3 3 0 0 0 0 .8l-2 1.6a1 1 0 0 0-.2 1.3l1.9 3.2a1 1 0 0 0 1.2.4l2.3-.9a7 7 0 0 0 1.3.8l.4 2.4a1 1 0 0 0 1 .9h3a1 1 0 0 0 1-.9l.4-2.4a7 7 0 0 0 1.3-.8l2.3.9a1 1 0 0 0 1.2-.4l1.9-3.1a1 1 0 0 0-.2-1.3l-2-1.7Z",
);

export const DirectoryIcon = createIcon(
  "M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-5h-6v5H5a1 1 0 0 1-1-1v-8.5Z",
);

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
