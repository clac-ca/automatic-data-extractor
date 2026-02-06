import { lazy, type ReactElement } from "react";

import { PageState } from "@/components/layout";

const DocumentsListPage = lazy(() => import("@/pages/Workspace/sections/Documents"));
const DocumentsDetailPage = lazy(async () => {
  const module = await import("@/pages/Workspace/sections/Documents");
  return { default: module.DocumentsDetailPage };
});
const RunsScreen = lazy(() => import("@/pages/Workspace/sections/Runs"));
const ConfigBuilderScreen = lazy(() => import("@/pages/Workspace/sections/ConfigBuilder"));
const ConfigurationDetailScreen = lazy(() => import("@/pages/Workspace/sections/ConfigBuilder/detail"));
const ConfigBuilderWorkbenchScreen = lazy(() => import("@/pages/Workspace/sections/ConfigBuilder/workbench"));
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
  "config-builder": resolveConfigBuilderSection,
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

function resolveConfigBuilderSection(segments: string[]): WorkspaceSectionRender {
  const [, maybeConfigId, maybeMode] = segments;
  if (!maybeConfigId) {
    return createSectionContent("config-builder", <ConfigBuilderScreen />);
  }
  const configId = decodeURIComponent(maybeConfigId);
  if (maybeMode === "editor") {
    return createSectionContent(
      `config-builder:${maybeConfigId}:editor`,
      <ConfigBuilderWorkbenchScreenWithParams configId={configId} />,
      { fullHeight: true },
    );
  }
  return createSectionContent(
    `config-builder:${maybeConfigId}`,
    <ConfigurationDetailScreen params={{ configId }} />,
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

function ConfigBuilderWorkbenchScreenWithParams({ configId }: { readonly configId: string }) {
  return <ConfigBuilderWorkbenchScreen params={{ configId }} />;
}
