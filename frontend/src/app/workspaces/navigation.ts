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
  data: {
    type: "static",
    items: [
      (workspaceId) => ({ id: "data-sources", label: "Sources", href: `/workspaces/${workspaceId}/data?view=sources` }),
      (workspaceId) => ({ id: "data-schemas", label: "Schemas", href: `/workspaces/${workspaceId}/data?view=schemas` }),
      (workspaceId) => ({ id: "data-exports", label: "Exports", href: `/workspaces/${workspaceId}/data?view=exports` }),
    ],
    emptyLabel: "Add a connector to populate data views.",
  },
  config: {
    type: "static",
    items: [
      (workspaceId) => ({ id: "config-connectors", label: "Connectors", href: `/workspaces/${workspaceId}/config?view=connectors` }),
      (workspaceId) => ({ id: "config-webhooks", label: "Webhooks", href: `/workspaces/${workspaceId}/config?view=webhooks` }),
      (workspaceId) => ({ id: "config-automation", label: "Automations", href: `/workspaces/${workspaceId}/config?view=automations` }),
    ],
    emptyLabel: "Configure integrations to unlock additional controls.",
  },
  settings: {
    type: "static",
    items: [
      (workspaceId) => ({ id: "settings-profile", label: "Workspace profile", href: `/workspaces/${workspaceId}/settings?view=profile` }),
      (workspaceId) => ({ id: "settings-permissions", label: "Members & access", href: `/workspaces/${workspaceId}/settings?view=permissions` }),
      (workspaceId) => ({ id: "settings-retention", label: "Retention", href: `/workspaces/${workspaceId}/settings?view=retention` }),
    ],
    emptyLabel: "Workspace settings will appear here soon.",
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
