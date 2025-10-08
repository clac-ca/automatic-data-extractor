import { useEffect, useState } from "react";
import { Outlet, useNavigate, useParams } from "react-router-dom";

import type { SessionEnvelope, WorkspaceProfile } from "../../../shared/api/types";
import { CreateWorkspaceForm } from "./CreateWorkspaceForm";
import { useWorkspacesQuery } from "../hooks/useWorkspacesQuery";
import { useSessionQuery } from "../../auth/hooks/useSessionQuery";

export function WorkspaceLayout() {
  const { data, isLoading, error } = useWorkspacesQuery();
  const sessionQuery = useSessionQuery();
  const session = sessionQuery.data ?? null;
  const navigate = useNavigate();
  const params = useParams<{ workspaceId?: string }>();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  const canCreateWorkspaces = canUserCreateWorkspaces(session ?? null);

  if (isLoading || (sessionQuery.isLoading && typeof sessionQuery.data === "undefined")) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Loading workspaces…
      </div>
    );
  }

  if (sessionQuery.error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to confirm your session.</p>
        <a href="/login" className="font-medium text-sky-300 hover:text-sky-200">
          Return to sign in
        </a>
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

  const workspaces = data ?? [];
  const hasWorkspaces = workspaces.length > 0;
  const showEmptyState = !hasWorkspaces;

  const resolvedWorkspaceId =
    params.workspaceId || session?.user.preferred_workspace_id || workspaces[0]?.id || undefined;

  useEffect(() => {
    if (!params.workspaceId && resolvedWorkspaceId) {
      navigate(`/workspaces/${resolvedWorkspaceId}`, { replace: true });
    }
  }, [params.workspaceId, resolvedWorkspaceId, navigate]);

  const activeWorkspace = workspaces.find((workspace) => workspace.id === resolvedWorkspaceId) ?? workspaces[0];

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <WorkspaceTopBar
        session={session ?? null}
        workspaces={workspaces}
        activeWorkspaceId={activeWorkspace?.id}
        onSelectWorkspace={(workspaceId) => navigate(`/workspaces/${workspaceId}`)}
        canCreateWorkspaces={canCreateWorkspaces}
        onCreateWorkspace={() => setIsCreateDialogOpen(true)}
      />
      <div className="flex flex-1">
        <WorkspaceSidebar
          workspaces={workspaces}
          activeWorkspaceId={activeWorkspace?.id}
          onSelectWorkspace={(workspaceId) => navigate(`/workspaces/${workspaceId}`)}
        />
        <main className="flex flex-1 flex-col">
          {showEmptyState ? (
            <WorkspaceEmptyState
              canCreateWorkspaces={canCreateWorkspaces}
              onCreateWorkspace={() => setIsCreateDialogOpen(true)}
              session={session ?? null}
            />
          ) : (
            <>
              <WorkspaceHeader workspace={activeWorkspace} />
              <div className="flex-1 overflow-y-auto px-8 py-10">
                <Outlet context={{ workspace: activeWorkspace }} />
              </div>
            </>
          )}
        </main>
      </div>
      <CreateWorkspaceDialog
        open={isCreateDialogOpen}
        onClose={() => setIsCreateDialogOpen(false)}
        onCreated={(workspace) => {
          setIsCreateDialogOpen(false);
          navigate(`/workspaces/${workspace.id}`);
        }}
      />
    </div>
  );
}

function WorkspaceHeader({ workspace }: { workspace?: WorkspaceProfile }) {
  const name = workspace?.name ?? "Workspace";
  const roleLabel = workspace?.role === "owner" ? "Owner" : workspace?.role === "member" ? "Member" : undefined;
  const subtitleParts = [roleLabel ? `Role: ${roleLabel}` : null, workspace?.slug ? `Slug: ${workspace.slug}` : null].filter(
    Boolean,
  );
  const subtitle =
    subtitleParts.length > 0 ? subtitleParts.join(" • ") : "Monitor extraction activity and review configuration details.";

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-900 bg-slate-950/70 px-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">{name}</h1>
        <p className="text-xs text-slate-500">{subtitle}</p>
      </div>
    </header>
  );
}

interface WorkspaceTopBarProps {
  session: SessionEnvelope | null;
  workspaces: WorkspaceProfile[];
  activeWorkspaceId?: string;
  onSelectWorkspace: (workspaceId: string) => void;
  canCreateWorkspaces: boolean;
  onCreateWorkspace: () => void;
}

function WorkspaceTopBar({
  session,
  workspaces,
  activeWorkspaceId,
  onSelectWorkspace,
  canCreateWorkspaces,
  onCreateWorkspace,
}: WorkspaceTopBarProps) {
  const hasWorkspaces = workspaces.length > 0;
  const activeValue = activeWorkspaceId ?? (hasWorkspaces ? workspaces[0]?.id ?? "" : "");

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-900 bg-slate-950/80 px-6">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold uppercase tracking-[0.32em] text-sky-300">ADE</span>
          <span className="hidden text-sm font-medium text-slate-400 sm:block">Automatic Data Extractor</span>
        </div>
        <div className="flex items-center gap-2">
          {hasWorkspaces ? (
            <>
              <label htmlFor="workspace-selector" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Workspace
              </label>
              <select
                id="workspace-selector"
                name="workspace"
                className="rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
                value={activeValue}
                onChange={(event) => {
                  const nextWorkspaceId = event.target.value;
                  if (nextWorkspaceId) {
                    onSelectWorkspace(nextWorkspaceId);
                  }
                }}
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </>
          ) : (
            <>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Workspace</span>
              <span className="text-sm text-slate-500">No workspaces yet</span>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-4">
        {canCreateWorkspaces && (
          <button
            type="button"
            onClick={onCreateWorkspace}
            className="inline-flex items-center rounded border border-sky-500 bg-sky-500/10 px-3 py-2 text-sm font-semibold text-sky-200 transition hover:bg-sky-500/20 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            + New workspace
          </button>
        )}
        <div className="hidden text-right text-sm sm:block">
          <p className="font-medium text-slate-100">{session?.user.display_name ?? session?.user.email ?? ""}</p>
          <p className="text-xs text-slate-500">{session?.user.email ?? ""}</p>
        </div>
        <a
          href="/logout"
          className="rounded border border-transparent px-3 py-2 text-sm font-medium text-slate-300 transition hover:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
        >
          Sign out
        </a>
      </div>
    </header>
  );
}

interface WorkspaceSidebarProps {
  workspaces: WorkspaceProfile[];
  activeWorkspaceId?: string;
  onSelectWorkspace: (workspaceId: string) => void;
}

function WorkspaceSidebar({ workspaces, activeWorkspaceId, onSelectWorkspace }: WorkspaceSidebarProps) {
  if (workspaces.length === 0) {
    return null;
  }

  return (
    <aside className="hidden w-72 border-r border-slate-900 bg-slate-950/80 p-4 lg:flex lg:flex-col">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Workspaces</h2>
        <ul className="mt-2 space-y-1 text-sm">
          {workspaces.map((workspace) => (
            <li key={workspace.id}>
              <button
                type="button"
                onClick={() => onSelectWorkspace(workspace.id)}
                className={`w-full rounded px-3 py-2 text-left transition ${
                  workspace.id === activeWorkspaceId
                    ? "bg-slate-900 text-slate-50"
                    : "text-slate-400 hover:bg-slate-900/70 hover:text-slate-100"
                }`}
              >
                <div className="font-medium">{workspace.name}</div>
                <div className="text-xs text-slate-500">
                  {[
                    workspace.role === "owner" ? "Owner" : "Member",
                    workspace.slug,
                    workspace.is_default ? "Default" : null,
                  ]
                    .filter(Boolean)
                    .join(" • ")}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

interface CreateWorkspaceDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (workspace: WorkspaceProfile) => void;
}

function CreateWorkspaceDialog({ open, onClose, onCreated }: CreateWorkspaceDialogProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-workspace-title"
        className="w-full max-w-lg rounded border border-slate-900 bg-slate-950 p-6 text-slate-100 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="create-workspace-title" className="text-xl font-semibold">
              Create workspace
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Name your workspace. You can invite teammates from the workspace settings after creation.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close create workspace dialog"
            className="rounded border border-transparent p-1 text-slate-400 transition hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <div className="mt-6">
          <CreateWorkspaceForm onCreated={onCreated} onCancel={onClose} autoFocus />
        </div>
      </div>
    </div>
  );
}

interface WorkspaceEmptyStateProps {
  canCreateWorkspaces: boolean;
  onCreateWorkspace: () => void;
  session: SessionEnvelope | null;
}

function WorkspaceEmptyState({ canCreateWorkspaces, onCreateWorkspace, session }: WorkspaceEmptyStateProps) {
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
              className="inline-flex items-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
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
        {session?.user.email ? (
          <p className="text-xs text-slate-500">Signed in as {session.user.email}</p>
        ) : null}
      </div>
    </div>
  );
}

function canUserCreateWorkspaces(session: SessionEnvelope | null): boolean {
  if (!session?.user || session.user.is_service_account) {
    return false;
  }

  const normalizedRole = String(session.user.role).toLowerCase();
  if (normalizedRole === "admin") {
    return true;
  }

  const permissions = Array.isArray(session.user.permissions) ? session.user.permissions : [];
  return permissions
    .map((permission) => permission.toLowerCase())
    .some((permission) =>
      permission === "workspace:create" ||
      permission === "workspaces:create" ||
      permission.startsWith("workspace:create:") ||
      permission.startsWith("workspaces:create:")
    );
}
