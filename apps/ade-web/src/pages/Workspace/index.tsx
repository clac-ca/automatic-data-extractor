import { useEffect, useMemo, type ReactElement } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS } from "@/hooks/workspaces";
import { writePreferredWorkspaceId } from "@/lib/workspacePreferences";
import type { WorkspaceProfile } from "@/types/workspaces";
import { WorkspaceProvider } from "@/pages/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider } from "@/pages/Workspace/context/WorkbenchWindowContext";
import { defaultWorkspaceSection, getWorkspacePrimaryNavigation } from "@/pages/Workspace/components/workspace-sidebar";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@/hooks/system";
import { PageState } from "@/components/layout";
import { WorkspaceLayout } from "@/app/layouts/WorkspaceLayout";

import DocumentsScreen from "@/pages/Workspace/sections/Documents";
import RunsScreen from "@/pages/Workspace/sections/Runs";
import ConfigBuilderScreen from "@/pages/Workspace/sections/ConfigBuilder";
import ConfigurationDetailScreen from "@/pages/Workspace/sections/ConfigBuilder/detail";
import ConfigBuilderWorkbenchScreen from "@/pages/Workspace/sections/ConfigBuilder/workbench";
import WorkspaceSettingsScreen from "@/pages/Workspace/sections/Settings";

type WorkspaceSectionRender =
  | { readonly kind: "redirect"; readonly to: string }
  | {
      readonly kind: "content";
      readonly key: string;
      readonly element: ReactElement;
      readonly fullHeight?: boolean;
      readonly fullWidth?: boolean;
    };

export default function WorkspaceScreen() {
  return <WorkspaceContent />;
}

function WorkspaceContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data?.items],
  );
  const identifier = extractWorkspaceIdentifier(location.pathname);
  const workspace = useMemo(() => findWorkspace(workspaces, identifier), [workspaces, identifier]);

  useEffect(() => {
    if (workspacesQuery.data) {
      queryClient.setQueryData(
        workspacesKeys.list(WORKSPACE_LIST_DEFAULT_PARAMS),
        workspacesQuery.data,
      );
    }
  }, [queryClient, workspacesQuery.data]);

  useEffect(() => {
    if (!workspacesQuery.isLoading && !workspacesQuery.isError && workspaces.length === 0) {
      navigate("/workspaces", { replace: true });
    }
  }, [workspacesQuery.isLoading, workspacesQuery.isError, workspaces.length, navigate]);

  useEffect(() => {
    if (workspace && !identifier) {
      navigate(`/workspaces/${workspace.id}/${defaultWorkspaceSection.path}${location.search}${location.hash}`, {
        replace: true,
      });
    }
  }, [workspace, identifier, location.search, location.hash, navigate]);

  useEffect(() => {
    if (!workspace || !identifier) {
      return;
    }

    if (identifier !== workspace.id) {
      const canonical = buildCanonicalPath(location.pathname, location.search, workspace.id, identifier);
      if (canonical !== location.pathname + location.search) {
        navigate(canonical + location.hash, { replace: true });
      }
    }
  }, [workspace, identifier, location.pathname, location.search, location.hash, navigate]);

  useEffect(() => {
    if (workspace) {
      writePreferredWorkspaceId(workspace.id);
    }
  }, [workspace]);


  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-full items-center justify-center bg-background px-6">
        <PageState title="Loading workspace" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-full flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <PageState
          title="Unable to load workspace"
          description="We were unable to fetch workspace information. Refresh the page to try again."
          variant="error"
        />
        <button
          type="button"
          className="rounded-lg border border-border bg-card px-4 py-2 text-sm font-semibold text-muted-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          onClick={() => workspacesQuery.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!workspace) {
    return null;
  }

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceShell workspace={workspace} />
    </WorkspaceProvider>
  );
}

interface WorkspaceShellProps {
  readonly workspace: WorkspaceProfile;
}

function WorkspaceShell({ workspace }: WorkspaceShellProps) {
  return (
    <WorkbenchWindowProvider workspaceId={workspace.id}>
      <WorkspaceShellLayout workspace={workspace} />
    </WorkbenchWindowProvider>
  );
}

function WorkspaceShellLayout({ workspace }: WorkspaceShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const workspaceNavItems = useMemo(
    () => getWorkspacePrimaryNavigation(workspace),
    [workspace],
  );

  const segments = extractSectionSegments(location.pathname, workspace.id);
  const section = resolveWorkspaceSection(workspace.id, segments, location.search, location.hash);

  useEffect(() => {
    if (section?.kind === "redirect") {
      navigate(section.to, { replace: true });
    }
  }, [section, navigate]);

  if (!section || section.kind === "redirect") {
    return null;
  }

  return (
    <WorkspaceLayout
      workspace={workspace}
      navItems={workspaceNavItems}
      contentKey={section.key}
      fullHeight={section.fullHeight}
      fullWidth={section.fullWidth}
      safeModeEnabled={safeModeEnabled}
      safeModeDetail={safeModeDetail}
    >
      {section.element}
    </WorkspaceLayout>
  );
}

function extractWorkspaceIdentifier(pathname: string) {
  const match = pathname.match(/^\/workspaces\/([^/]+)/);
  return match?.[1] ?? null;
}

function extractSectionSegments(pathname: string, workspaceId: string) {
  const base = `/workspaces/${workspaceId}`;
  if (!pathname.startsWith(base)) {
    return [];
  }
  const remainder = pathname.slice(base.length);
  return remainder
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
}

function findWorkspace(workspaces: WorkspaceProfile[], identifier: string | null) {
  if (!identifier) {
    return workspaces[0] ?? null;
  }
  return (
    workspaces.find((workspace) => workspace.id === identifier) ??
    workspaces.find((workspace) => workspace.slug === identifier) ??
    workspaces[0] ??
    null
  );
}

function buildCanonicalPath(pathname: string, search: string, resolvedId: string, currentId: string) {
  const base = `/workspaces/${currentId}`;
  const trailing = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  const normalized = trailing && trailing !== "/" ? trailing : `/${defaultWorkspaceSection.path}`;
  return `/workspaces/${resolvedId}${normalized}${search}`;
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
      to: `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}${suffix}`,
    };
  }

  const [first, second, third] = segments;
  switch (first) {
    case defaultWorkspaceSection.path:
    case "documents": {
      if (second) {
        const params = new URLSearchParams(search);
        params.set("doc", decodeURIComponent(second));
        const query = params.toString();
        return {
          kind: "redirect",
          to: `/workspaces/${workspaceId}/documents${query ? `?${query}` : ""}${hash}`,
        };
      }
      return {
        kind: "content",
        key: "documents",
        element: <DocumentsScreen />,
        fullWidth: true,
        fullHeight: true,
      };
    }
    case "runs":
      return { kind: "content", key: "runs", element: <RunsScreen />, fullWidth: true };
    case "config-builder": {
      if (!second) {
        return { kind: "content", key: "config-builder", element: <ConfigBuilderScreen /> };
      }
      if (third === "editor") {
        return {
          kind: "content",
          key: `config-builder:${second}:editor`,
          element: <ConfigBuilderWorkbenchScreenWithParams configId={decodeURIComponent(second)} />,
          fullHeight: true,
        };
      }
      return {
        kind: "content",
        key: `config-builder:${second}`,
        element: <ConfigurationDetailScreen params={{ configId: decodeURIComponent(second) }} />,
      };
    }
    case "settings": {
      const remaining = segments.slice(1);
      const normalized = remaining.length > 0 ? remaining : [];
      const key = `settings:${normalized.length > 0 ? normalized.join(":") : "general"}`;
      return { kind: "content", key, element: <WorkspaceSettingsScreen sectionSegments={normalized} /> };
    }
    default:
      return {
        kind: "content",
        key: `not-found:${segments.join("/")}`,
        element: (
          <PageState
            title="Section not found"
            description="The requested workspace section could not be located."
            variant="error"
          />
        ),
      };
  }
}
function ConfigBuilderWorkbenchScreenWithParams({ configId }: { readonly configId: string }) {
  return <ConfigBuilderWorkbenchScreen params={{ configId }} />;
}
