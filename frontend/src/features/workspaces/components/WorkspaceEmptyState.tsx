import type { SessionEnvelope } from "../../../shared/api/types";

interface WorkspaceEmptyStateProps {
  canCreateWorkspaces: boolean;
  onCreateWorkspace: () => void;
  session: SessionEnvelope | null;
}

export function WorkspaceEmptyState({ canCreateWorkspaces, onCreateWorkspace, session }: WorkspaceEmptyStateProps) {
  if (canCreateWorkspaces) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-16">
        <div className="w-full max-w-xl space-y-6 rounded border border-slate-900 bg-slate-950/80 p-10 text-center text-slate-100 shadow-lg">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold">Create your first workspace</h1>
            <p className="text-sm text-slate-400">
              Workspaces keep your extraction projects, configurations, and members organized. Create one to get started.
            </p>
          </div>
          <div className="flex justify-center">
            <button
              type="button"
              onClick={onCreateWorkspace}
              className="inline-flex items-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
            >
              Create workspace
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 items-center justify-center px-6 py-12 text-center text-sm text-slate-300">
      <div className="space-y-3">
        <p>No workspaces are available for your account yet. Ask an administrator to grant access.</p>
        {session?.user.email ? <p className="text-xs text-slate-500">Signed in as {session.user.email}</p> : null}
      </div>
    </div>
  );
}
