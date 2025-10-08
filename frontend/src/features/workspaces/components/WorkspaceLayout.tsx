import { useEffect } from "react";
import { NavLink, Outlet, useNavigate, useOutletContext, useParams } from "react-router-dom";

import { useWorkspacesQuery } from "../hooks/useWorkspacesQuery";
import type { SessionEnvelope } from "../../../shared/api/types";
import { formatDateTime } from "../../../shared/dates";

export function WorkspaceLayout() {
  const { data, isLoading, error } = useWorkspacesQuery();
  const session = useOutletContext<SessionEnvelope | null>();
  const navigate = useNavigate();
  const params = useParams<{ workspaceId?: string }>();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Loading workspaces…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to load your workspaces.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
  }

  const workspaces = data?.workspaces ?? [];

  if (workspaces.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center text-center text-sm text-slate-300">
        No workspaces are available for your account yet. Ask an administrator to grant access.
      </div>
    );
  }

  const resolvedWorkspaceId =
    params.workspaceId || session?.user.preferred_workspace_id || workspaces[0]?.id || undefined;

  useEffect(() => {
    if (!params.workspaceId && resolvedWorkspaceId) {
      navigate(`/workspaces/${resolvedWorkspaceId}`, { replace: true });
    }
  }, [params.workspaceId, resolvedWorkspaceId, navigate]);

  const activeWorkspace = workspaces.find((workspace) => workspace.id === resolvedWorkspaceId) ?? workspaces[0];
  const documentTypes = activeWorkspace?.document_types ?? [];

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="flex w-72 flex-col border-r border-slate-900 bg-slate-950/80 p-4">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-slate-200">Workspaces</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {workspaces.map((workspace) => (
              <li key={workspace.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/workspaces/${workspace.id}`)}
                  className={`w-full rounded px-3 py-2 text-left ${
                    workspace.id === activeWorkspace?.id
                      ? "bg-slate-900 text-slate-50"
                      : "text-slate-400 hover:bg-slate-900/70 hover:text-slate-100"
                  }`}
                >
                  <div className="font-medium">{workspace.name}</div>
                  <div className="text-xs text-slate-500">{workspace.status}</div>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Document types</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {documentTypes.map((documentType) => (
              <li key={documentType.id}>
                <NavLink
                  to={`/workspaces/${activeWorkspace?.id ?? ""}/document-types/${documentType.id}`}
                  className={({ isActive }) =>
                    `block rounded px-3 py-2 ${
                      isActive
                        ? "bg-sky-500/20 text-sky-200"
                        : "text-slate-400 hover:bg-slate-900/70 hover:text-slate-100"
                    }`
                  }
                >
                  <div className="font-medium">{documentType.display_name}</div>
                  <div className="text-xs text-slate-500">Last run {formatDateTime(documentType.last_run_at)}</div>
                </NavLink>
              </li>
            ))}
            {documentTypes.length === 0 && (
              <li className="px-3 py-2 text-xs text-slate-500">No document types yet.</li>
            )}
          </ul>
        </div>
        <div className="mt-6 border-t border-slate-900 pt-4 text-xs text-slate-500">
          <p className="font-medium text-slate-300">{session?.user.display_name ?? ""}</p>
          <p>{session?.user.email ?? ""}</p>
          <a href="/logout" className="mt-3 inline-block text-slate-300 hover:text-slate-100">
            Sign out
          </a>
        </div>
      </aside>
      <main className="flex flex-1 flex-col">
        <WorkspaceHeader workspaceName={activeWorkspace?.name ?? "Workspace"} />
        <div className="flex-1 overflow-y-auto px-8 py-10">
          <Outlet context={{ workspace: activeWorkspace }} />
        </div>
      </main>
    </div>
  );
}

function WorkspaceHeader({ workspaceName }: { workspaceName: string }) {
  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-900 bg-slate-950/70 px-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">{workspaceName}</h1>
        <p className="text-xs text-slate-500">Monitor extraction activity and review configuration details.</p>
      </div>
    </header>
  );
}

