import { useCallback, useMemo, useState } from "react";

import { Link } from "@app/nav/Link";
import { useNavigate } from "@app/nav/history";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery, type WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";
import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";
import { defaultWorkspaceSection } from "@screens/Workspace/components/workspace-navigation";
import { WorkspaceDirectoryLayout } from "@screens/Workspaces/components/WorkspaceDirectoryLayout";
import { useShortcutHint } from "@shared/hooks/useShortcutHint";
import type { GlobalSearchSuggestion } from "@app/shell/GlobalTopBar";

export default function WorkspacesIndexRoute() {
  return (
    <RequireSession>
      <WorkspacesIndexContent />
    </RequireSession>
  );
}

function WorkspacesIndexContent() {
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();
  const userPermissions = session.user.permissions ?? [];
  const canCreateWorkspace = userPermissions.includes("Workspaces.Create");
  const [searchQuery, setSearchQuery] = useState("");
  const shortcutHint = useShortcutHint();

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Loading workspaces" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState
          title="We couldn't load your workspaces"
          description="Refresh the page or try again later."
          variant="error"
          action={
            <Button variant="secondary" onClick={() => workspacesQuery.refetch()}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  const workspacesPage = workspacesQuery.data;
  const workspaces: WorkspaceProfile[] = workspacesPage?.items ?? [];
  const normalizedSearch = searchQuery.trim().toLowerCase();
  const visibleWorkspaces = useMemo(() => {
    if (!normalizedSearch) {
      return workspaces;
    }
    return workspaces.filter((workspace) => {
      const name = workspace.name.toLowerCase();
      const slug = workspace.slug?.toLowerCase() ?? "";
      return name.includes(normalizedSearch) || slug.includes(normalizedSearch);
    });
  }, [workspaces, normalizedSearch]);

  const actions = canCreateWorkspace ? (
    <Button variant="primary" onClick={() => navigate("/workspaces/new")}>Create workspace</Button>
  ) : undefined;

  const handleWorkspaceSearchSubmit = useCallback(() => {
    if (!normalizedSearch) {
      return;
    }
    const firstMatch = visibleWorkspaces[0];
    if (firstMatch) {
      navigate(`/workspaces/${firstMatch.id}/${defaultWorkspaceSection.path}`);
    }
  }, [visibleWorkspaces, normalizedSearch, navigate]);

  const handleResetSearch = useCallback(() => setSearchQuery(""), []);

  const suggestionSeed = (normalizedSearch ? visibleWorkspaces : workspaces).slice(0, 5);
  const searchSuggestions = suggestionSeed.map((workspace) => ({
    id: workspace.id,
    label: workspace.name,
    description: workspace.slug ? `Slug • ${workspace.slug}` : "Workspace",
  }));

  const handleWorkspaceSuggestionSelect = useCallback(
    (suggestion: GlobalSearchSuggestion) => {
      setSearchQuery("");
      navigate(`/workspaces/${suggestion.id}/${defaultWorkspaceSection.path}`);
    },
    [navigate],
  );

  const directorySearch = {
    value: searchQuery,
    onChange: setSearchQuery,
    onSubmit: handleWorkspaceSearchSubmit,
    placeholder: "Search workspaces or jump to one instantly",
    shortcutHint,
    scopeLabel: "Workspace directory",
    suggestions: searchSuggestions,
    onSelectSuggestion: handleWorkspaceSuggestionSelect,
  };

  const mainContent =
    workspaces.length === 0 ? (
      canCreateWorkspace ? (
        <EmptyStateCreate onCreate={() => navigate("/workspaces/new")} />
      ) : (
        <div className="space-y-4">
          <h1 id="page-title" className="sr-only">
            Workspaces
          </h1>
          <PageState
            title="No workspaces available"
            description="You don't have access to any workspaces yet. Ask an administrator to add you or create one on your behalf."
            variant="empty"
          />
        </div>
      )
    ) : visibleWorkspaces.length === 0 ? (
      <div className="space-y-4">
        <PageState
          title={`No workspaces matching "${searchQuery}"`}
          description="Try searching by another workspace name or slug."
          action={
            <Button variant="secondary" onClick={handleResetSearch}>
              Clear search
            </Button>
          }
        />
      </div>
    ) : (
      <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header>
          <h1 id="page-title" className="text-2xl font-semibold text-slate-900">
            Workspaces
          </h1>
          <p className="mt-1 text-sm text-slate-500">Select a workspace to jump straight into documents.</p>
        </header>
        <section className="grid gap-5 lg:grid-cols-2">
          {visibleWorkspaces.map((workspace) => (
            <Link
              key={workspace.id}
              to={`/workspaces/${workspace.id}/${defaultWorkspaceSection.path}`}
              className="group rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">{workspace.name}</h2>
                {workspace.is_default ? (
                  <span className="rounded-full bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-600">Default</span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-slate-500">Slug: {workspace.slug}</p>
              <p className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-500">Permissions</p>
              <p className="text-sm text-slate-600">
                {workspace.permissions.length > 0 ? workspace.permissions.join(", ") : "None"}
              </p>
            </Link>
          ))}
        </section>
      </div>
    );

  return (
    <WorkspaceDirectoryLayout
      actions={actions}
      search={directorySearch}
      sidePanel={<DirectorySidebar canCreate={canCreateWorkspace} onCreate={() => navigate("/workspaces/new")} />}
    >
      {mainContent}
    </WorkspaceDirectoryLayout>
  );
}

function DirectorySidebar({ canCreate, onCreate }: { canCreate: boolean; onCreate: () => void }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Workspace tips</p>
          <h2 className="text-sm font-semibold text-slate-900">Why multiple workspaces?</h2>
        </header>
        <p className="text-xs text-slate-500 leading-relaxed">
          Segment teams by business unit or client, control access with roles, and tailor extraction settings per
          workspace. Everything stays organised and secure.
        </p>
        {canCreate ? (
          <Button variant="secondary" onClick={onCreate} className="w-full">
            New workspace
          </Button>
        ) : null}
      </section>
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Need a hand?</p>
          <h2 className="text-sm font-semibold text-slate-900">Workspace setup checklist</h2>
        </header>
        <ul className="space-y-2 text-xs text-slate-600">
          <li>Invite at least one additional administrator.</li>
          <li>Review configurations before uploading production files.</li>
          <li>Review workspace permissions for external collaborators.</li>
        </ul>
      </section>
    </div>
  );
}


function EmptyStateCreate({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="mx-auto max-w-3xl rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-soft">
      <h1 id="page-title" className="text-2xl font-semibold text-slate-900">No workspaces yet</h1>
      <p className="mt-2 text-sm text-slate-600">
        Create your first workspace to start uploading configuration sets and documents.
      </p>
      <Button variant="primary" onClick={onCreate} className="mt-6">
        Create workspace
      </Button>
    </div>
  );
}
