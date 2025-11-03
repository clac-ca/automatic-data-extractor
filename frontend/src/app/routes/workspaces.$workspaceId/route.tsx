import { useEffect, useMemo, useState } from "react";
import type { ClientLoaderFunctionArgs, ShouldRevalidateFunctionArgs } from "react-router";
import { Outlet, redirect, useLoaderData, useLocation, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { ApiError } from "@shared/api";
import { buildLoginRedirect } from "@shared/auth/utils/authNavigation";
import { fetchWorkspaces, workspacesKeys, type WorkspaceProfile } from "../workspaces/workspaces-api";
import { WorkspaceProvider } from "./WorkspaceContext";
import { createScopedStorage } from "@shared/storage";
import { writePreferredWorkspace } from "../workspaces/workspace-preferences";
import { GlobalTopBar } from "../workspaces/GlobalTopBar";
import { ProfileDropdown } from "../workspaces/ProfileDropdown";
import { WorkspaceNav } from "./WorkspaceNav";
import { defaultWorkspaceSection } from "../workspaces/workspace-navigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import { Alert } from "@ui/alert";

export interface WorkspaceLoaderData {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: WorkspaceProfile[];
}

export async function clientLoader({
  params,
  request,
}: ClientLoaderFunctionArgs): Promise<WorkspaceLoaderData> {
  try {
    const workspaces = await fetchWorkspaces(request.signal);

    if (workspaces.length === 0) {
      throw redirectToDirectory();
    }

    const resolved = findWorkspace(workspaces, params.workspaceId);

    if (!resolved) {
      throw redirectToDirectory();
    }

    if (!params.workspaceId || params.workspaceId !== resolved.id) {
      const canonicalPath = buildCanonicalPath(request.url, params.workspaceId, resolved.id);
      throw redirect(canonicalPath);
    }

    return { workspace: resolved, workspaces };
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      const url = new URL(request.url);
      const loginRedirect = buildLoginRedirect(`${url.pathname}${url.search}${url.hash}`);
      throw redirect(loginRedirect);
    }
    throw error;
  }
}

export function clientShouldRevalidate({
  currentParams,
  nextParams,
}: ShouldRevalidateFunctionArgs) {
  return currentParams.workspaceId !== nextParams.workspaceId;
}

export function getDefaultWorkspacePath(workspaceId: string) {
  return `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}`;
}

export default function WorkspaceRoute() {
  const { workspace, workspaces } = useLoaderData<WorkspaceLoaderData>();

  return (
    <RequireSession>
      <WorkspaceContent workspace={workspace} workspaces={workspaces} />
    </RequireSession>
  );
}

type WorkspaceContentProps = WorkspaceLoaderData;

function WorkspaceContent({ workspace, workspaces }: WorkspaceContentProps) {
  const queryClient = useQueryClient();

  useEffect(() => {
    queryClient.setQueryData(workspacesKeys.list(), workspaces);
  }, [queryClient, workspaces]);

  useEffect(() => {
    writePreferredWorkspace(workspace);
  }, [workspace]);

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
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;

  const navStorage = useMemo(
    () => createScopedStorage(`ade.ui.workspace.${workspace.id}.navCollapsed`),
    [workspace.id],
  );
  const [isNavCollapsed, setIsNavCollapsed] = useState(() => {
    const stored = navStorage.get<boolean>();
    return typeof stored === "boolean" ? stored : false;
  });

  useEffect(() => {
    const stored = navStorage.get<boolean>();
    setIsNavCollapsed(typeof stored === "boolean" ? stored : false);
  }, [navStorage]);

  useEffect(() => {
    navStorage.set(isNavCollapsed);
  }, [isNavCollapsed, navStorage]);

  const topBarLeading = (
    <button
      type="button"
      className="focus-ring inline-flex items-center gap-3 rounded-xl border border-transparent bg-white px-3 py-2 text-left text-sm font-semibold text-slate-900 shadow-sm transition hover:border-slate-200"
      onClick={() => navigate("/workspaces")}
    >
      <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm">
        ADE
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-semibold text-slate-900">{workspace.name}</span>
        <span className="text-xs text-slate-400">Workspace</span>
      </span>
    </button>
  );

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarTrailing = (
    <div className="flex items-center gap-2">
      <ProfileDropdown displayName={displayName} email={email} />
    </div>
  );

  const primaryNav = (
    <WorkspaceNav
      workspace={workspace}
      collapsed={isNavCollapsed}
      onToggleCollapse={() => setIsNavCollapsed((current) => !current)}
    />
  );

  const outletKey = `${location.pathname}${location.search}${location.hash}`;
  const sectionKey = (() => {
    const match = location.pathname.match(/\/workspaces\/[^/]+\/([^/?#]+)/);
    return match?.[1] ?? "";
  })();

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <GlobalTopBar leading={topBarLeading} trailing={topBarTrailing} />
      <div className="relative flex flex-1 overflow-hidden" key={`section-${sectionKey}`}>
        {primaryNav}
        <main className="relative flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6">
            {safeModeEnabled ? (
              <div className="mb-4">
                <Alert tone="warning" heading="Safe mode active">
                  {safeModeDetail}
                </Alert>
              </div>
            ) : null}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
              <Outlet key={outletKey} />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function findWorkspace(workspaces: WorkspaceProfile[], identifier: string | undefined | null) {
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

function buildCanonicalPath(requestUrl: string, currentId: string | undefined, resolvedId: string) {
  const url = new URL(requestUrl);
  const pathname = url.pathname;
  const search = url.search;

  const baseSegment = currentId ? `/workspaces/${currentId}` : "/workspaces";
  const trailing = pathname.startsWith(baseSegment) ? pathname.slice(baseSegment.length) : "";
  const normalisedTrailing = trailing && trailing !== "/" ? trailing : `/${defaultWorkspaceSection.path}`;

  return `/workspaces/${resolvedId}${normalisedTrailing}${search}`;
}

function redirectToDirectory() {
  return redirect("/workspaces");
}
