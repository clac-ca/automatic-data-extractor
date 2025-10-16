import type { ComponentType, SVGProps } from "react";

import type { WorkspaceProfile } from "../../shared/types/workspaces";
import type { WorkspaceSectionDescriptor, WorkspaceSectionId } from "./sections";
import { buildWorkspaceSectionPath, workspaceSections } from "./sections";
import {
  ConfigureIcon,
  DataIcon,
  DocumentsIcon,
  OverviewIcon,
  RunsIcon,
  SettingsIcon,
} from "./icons";

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

const sectionIcons: Record<WorkspaceSectionId, ComponentType<SVGProps<SVGSVGElement>>> = {
  documents: DocumentsIcon,
  overview: OverviewIcon,
  runs: RunsIcon,
  data: DataIcon,
  config: ConfigureIcon,
  settings: SettingsIcon,
};

export function getWorkspacePrimaryNavItems(workspace: WorkspaceProfile): WorkspacePrimaryNavItem[] {
  return workspaceSections.map((section) => ({
    id: section.id,
    label: section.label,
    description: section.description,
    href: buildWorkspaceSectionPath(workspace.id, section.id),
    icon: sectionIcons[section.id],
  }));
}

type SecondaryDefinition = WorkspaceSecondaryNavItem | ((workspaceId: string) => WorkspaceSecondaryNavItem);

interface StaticSecondaryNavConfig {
  readonly type: "static";
  readonly items: readonly SecondaryDefinition[];
  readonly emptyLabel?: string;
}

interface DynamicSecondaryNavConfig {
  readonly type: "dynamic";
  readonly emptyLabel?: string;
}

type SecondaryNavConfig = StaticSecondaryNavConfig | DynamicSecondaryNavConfig;

const secondaryDefinitions: Partial<Record<WorkspaceSectionId, SecondaryNavConfig>> = {
  documents: {
    type: "static",
    items: [
      (workspaceId) => ({ id: "documents-inbox", label: "Inbox", href: `/workspaces/${workspaceId}/documents?view=inbox` }),
      (workspaceId) => ({ id: "documents-processing", label: "Processing", href: `/workspaces/${workspaceId}/documents?view=processing` }),
      (workspaceId) => ({ id: "documents-completed", label: "Completed", href: `/workspaces/${workspaceId}/documents?view=completed` }),
      (workspaceId) => ({ id: "documents-failed", label: "Failed", href: `/workspaces/${workspaceId}/documents?view=failed` }),
      (workspaceId) => ({ id: "documents-archived", label: "Archived", href: `/workspaces/${workspaceId}/documents?view=archived` }),
      (workspaceId) => ({ id: "documents-saved", label: "Saved filters", href: `/workspaces/${workspaceId}/documents?view=saved` }),
    ],
    emptyLabel: "No saved document views yet.",
  },
  runs: {
    type: "static",
    items: [
      (workspaceId) => ({ id: "runs-active", label: "Active jobs", href: `/workspaces/${workspaceId}/runs?view=active` }),
      (workspaceId) => ({ id: "runs-history", label: "History", href: `/workspaces/${workspaceId}/runs?view=history` }),
      (workspaceId) => ({ id: "runs-alerts", label: "Alerts", href: `/workspaces/${workspaceId}/runs?view=alerts`, badge: "3" }),
    ],
    emptyLabel: "No job filters pinned yet.",
  },
  data: {
    type: "static",
    items: [
      (workspaceId) => ({ id: "data-datasets", label: "Datasets", href: `/workspaces/${workspaceId}/data?view=datasets` }),
      (workspaceId) => ({ id: "data-exports", label: "Exports", href: `/workspaces/${workspaceId}/data?view=exports` }),
    ],
  },
};

function resolveDefinition(definition: SecondaryDefinition, workspaceId: string): WorkspaceSecondaryNavItem {
  return typeof definition === "function" ? definition(workspaceId) : definition;
}

export function getWorkspaceSecondaryNavigation(
  workspaceId: string,
  section: WorkspaceSectionDescriptor,
): WorkspaceSecondaryNavigation {
  const config = secondaryDefinitions[section.id];
  const fallbackEmptyLabel = `No ${section.label.toLowerCase()} views yet.`;

  if (!config) {
    return { status: "empty", items: [], emptyLabel: fallbackEmptyLabel };
  }

  if (config.type === "dynamic") {
    return { status: "loading", items: [], emptyLabel: config.emptyLabel ?? fallbackEmptyLabel };
  }

  const items = config.items.map((definition) => resolveDefinition(definition, workspaceId));
  if (items.length === 0) {
    return { status: "empty", items: [], emptyLabel: config.emptyLabel ?? fallbackEmptyLabel };
  }
  return { status: "ready", items, emptyLabel: config.emptyLabel ?? fallbackEmptyLabel };
}
