import { lazy, type ReactElement } from "react";

import { PageState } from "@/components/layout";
import { CONFIGURATIONS_SECTION_SEGMENT } from "@/pages/Workspace/sections/ConfigurationEditor/paths";

const DocumentsListPage = lazy(() => import("@/pages/Workspace/sections/Documents"));
const DocumentsDetailPage = lazy(async () => {
  const module = await import("@/pages/Workspace/sections/Documents");
  return { default: module.DocumentsDetailPage };
});
const RunsScreen = lazy(() => import("@/pages/Workspace/sections/Runs"));
const ConfigurationEditorEntryRoute = lazy(() => import("@/pages/Workspace/sections/ConfigurationEditor"));
const ConfigurationEditorRoute = lazy(() => import("@/pages/Workspace/sections/ConfigurationEditor/workbench"));
const WorkspaceSettingsScreen = lazy(() => import("@/pages/Workspace/sections/Settings"));

export const DEFAULT_WORKSPACE_SECTION_PATH = "documents";

export type WorkspaceSectionRender =
  | { readonly kind: "redirect"; readonly to: string }
  | {
      readonly kind: "content";
      readonly key: string;
      readonly element: ReactElement;
      readonly fullHeight?: boolean;
      readonly fullWidth?: boolean;
    };
type WorkspaceSectionOptions = {
  readonly fullHeight?: boolean;
  readonly fullWidth?: boolean;
};
type WorkspaceSectionResolver = (segments: string[]) => WorkspaceSectionRender;

const workspaceSectionResolvers: Record<string, WorkspaceSectionResolver> = {
  [DEFAULT_WORKSPACE_SECTION_PATH]: resolveDocumentsSection,
  runs: resolveRunsSection,
  [CONFIGURATIONS_SECTION_SEGMENT]: resolveConfigurationEditorSection,
  settings: resolveSettingsSection,
};

function createSectionContent(
  key: string,
  element: ReactElement,
  options: WorkspaceSectionOptions = {},
): WorkspaceSectionRender {
  return { kind: "content", key, element, ...options };
}

function resolveDocumentsSection(segments: string[]): WorkspaceSectionRender {
  const [, maybeDocumentId] = segments;
  if (!maybeDocumentId) {
    return createSectionContent("documents", <DocumentsListPage />, {
      fullWidth: true,
      fullHeight: true,
    });
  }
  const documentId = decodeURIComponent(maybeDocumentId);
  return createSectionContent(`documents:${documentId}`, <DocumentsDetailPage documentId={documentId} />, {
    fullWidth: true,
    fullHeight: true,
  });
}

function resolveRunsSection(): WorkspaceSectionRender {
  return createSectionContent("runs", <RunsScreen />, { fullWidth: true });
}

function resolveConfigurationEditorSection(segments: string[]): WorkspaceSectionRender {
  const [, maybeConfigId] = segments;
  if (!maybeConfigId) {
    return createSectionContent("configurations", <ConfigurationEditorEntryRoute />, { fullHeight: true });
  }
  if (segments.length > 2) {
    return resolveUnknownSection(segments);
  }
  const configId = decodeURIComponent(maybeConfigId);
  return createSectionContent(
    `configurations:${maybeConfigId}`,
    <ConfigurationEditorRouteWithParams configId={configId} />,
    { fullHeight: true },
  );
}

function resolveSettingsSection(segments: string[]): WorkspaceSectionRender {
  const sectionSegments = segments.slice(1);
  const key = `settings:${sectionSegments.length > 0 ? sectionSegments.join(":") : "general"}`;
  return createSectionContent(key, <WorkspaceSettingsScreen sectionSegments={sectionSegments} />);
}

function resolveUnknownSection(segments: string[]): WorkspaceSectionRender {
  return createSectionContent(
    `not-found:${segments.join("/")}`,
    <PageState
      title="Section not found"
      description="The requested workspace section could not be located."
      variant="error"
    />,
  );
}

export function resolveWorkspaceSection(
  workspaceId: string,
  segments: string[],
  search: string,
  hash: string,
): WorkspaceSectionRender | null {
  const suffix = `${search}${hash}`;

  if (segments.length === 0) {
    return {
      kind: "redirect",
      to: `/workspaces/${workspaceId}/${DEFAULT_WORKSPACE_SECTION_PATH}${suffix}`,
    };
  }

  const [sectionName] = segments;
  const resolver = workspaceSectionResolvers[sectionName];
  return resolver ? resolver(segments) : resolveUnknownSection(segments);
}

function ConfigurationEditorRouteWithParams({ configId }: { readonly configId: string }) {
  return <ConfigurationEditorRoute params={{ configId }} />;
}
