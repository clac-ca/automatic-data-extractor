import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { DirectoryIcon } from "../workspaces/icons";
import { UserMenu, type UserMenuItem } from "./components/UserMenu";

export interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly sidePanel?: ReactNode;
  readonly actions?: ReactNode;
}

export function WorkspaceDirectoryLayout({ children, sidePanel, actions }: WorkspaceDirectoryLayoutProps) {
  const session = useSession();
  const logoutMutation = useLogoutMutation();
  const navigate = useNavigate();
  const profileItems: UserMenuItem[] = [];

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center gap-3 px-4 py-3">
          <button
            type="button"
            onClick={() => navigate("/workspaces")}
            className="flex items-center gap-3 rounded-lg px-2 py-1 text-left transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white shadow-sm">
              <DirectoryIcon className="h-5 w-5 text-white" />
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-slate-900">Workspace Directory</span>
              <span className="text-xs text-slate-500">Automatic Data Extractor</span>
            </span>
          </button>
          <div className="flex flex-1 items-center justify-end gap-3">
            {actions}
            <UserMenu
              displayName={session.user.display_name || session.user.email || "Signed in"}
              email={session.user.email ?? ""}
              items={profileItems}
              onSignOut={() => logoutMutation.mutate()}
              isSigningOut={logoutMutation.isPending}
            />
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div
          className={`mx-auto grid w-full max-w-6xl gap-6 px-4 py-8 ${sidePanel ? "lg:grid-cols-[minmax(0,1fr)_280px]" : ""}`}
        >
          <div>{children}</div>
          {sidePanel ? <aside className="space-y-6">{sidePanel}</aside> : null}
        </div>
      </main>
    </div>
  );
}
