import { useEffect, useMemo, useState } from "react";
import { Outlet, useLoaderData, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { WorkspaceProvider } from "../../../features/workspaces/context/WorkspaceContext";
import { workspacesKeys } from "../../../features/workspaces/api/keys";
import type { WorkspaceLoaderData } from "../../workspaces/loader";
import type { WorkspaceProfile } from "../../../shared/types/workspaces";
import { writePreferredWorkspace } from "../../../shared/lib/workspace";
import { createScopedStorage } from "../../../shared/lib/storage";
import { useSession } from "../../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../../features/auth/hooks/useLogoutMutation";
import { sessionKeys } from "../../../features/auth/sessionKeys";
import { GlobalTopBar } from "./components/GlobalTopBar";
import { ProfileDropdown } from "./components/ProfileDropdown";
import { WorkspaceNav } from "./components/WorkspaceNav";

export function WorkspaceLayout() {
  const { workspace, workspaces } = useLoaderData<WorkspaceLoaderData>();
  const queryClient = useQueryClient();

  useEffect(() => {
    queryClient.setQueryData(workspacesKeys.list(), workspaces);
  }, [queryClient, workspaces]);

  useEffect(() => {
    writePreferredWorkspace(workspace);
  }, [workspace]);

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceLayoutInner workspace={workspace} />
    </WorkspaceProvider>
  );
}

interface WorkspaceLayoutInnerProps {
  readonly workspace: WorkspaceProfile;
}

function WorkspaceLayoutInner({ workspace }: WorkspaceLayoutInnerProps) {
  const session = useSession();
  const logoutMutation = useLogoutMutation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  const navStorageKey = useMemo(() => `ade.ui.workspace.${workspace.id}.navCollapsed`, [workspace.id]);
  const navStorage = useMemo(() => createScopedStorage(navStorageKey), [navStorageKey]);
  const [isNavCollapsed, setIsNavCollapsed] = useState(false);

  useEffect(() => {
    const stored = navStorage.get<boolean>();
    if (typeof stored === "boolean") {
      setIsNavCollapsed((current) => (current === stored ? current : stored));
    }
  }, [navStorage]);

  useEffect(() => {
    navStorage.set(isNavCollapsed);
  }, [isNavCollapsed, navStorage]);

  const handleSignOut = () => {
    if (logoutMutation.isPending) {
      return;
    }
    queryClient.removeQueries({ queryKey: sessionKeys.providers(), exact: false });
    queryClient.setQueryData(sessionKeys.detail(), null);
    navigate("/login", { replace: true });
    logoutMutation.mutate();
  };

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
      <ProfileDropdown
        displayName={displayName}
        email={email}
        onSignOut={handleSignOut}
        signingOut={logoutMutation.isPending}
      />
    </div>
  );

  const primaryNav = (
    <WorkspaceNav
      workspace={workspace}
      collapsed={isNavCollapsed}
      onToggleCollapse={() => setIsNavCollapsed((current) => !current)}
      mobileOpen={false}
      onCloseMobile={() => undefined}
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
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
              <Outlet key={outletKey} />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
