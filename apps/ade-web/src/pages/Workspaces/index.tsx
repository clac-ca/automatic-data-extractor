import { useCallback, useMemo, useState } from "react";

import { useNavigate } from "@app/navigation/history";

import { useSession } from "@components/providers/auth/SessionContext";
import { useSetDefaultWorkspaceMutation, useWorkspacesQuery } from "@hooks/workspaces";
import { getDefaultWorkspacePath } from "@app/navigation/workspacePaths";
import { writePreferredWorkspaceId } from "@lib/workspacePreferences";
import type { WorkspaceProfile } from "@schema/workspaces";
import { Button } from "@/components/ui/button";
import { PageState } from "@components/layouts/page-state";
import { WorkspaceDirectoryLayout } from "@pages/Workspaces/components/WorkspaceDirectoryLayout";
import { GlobalNavSearch } from "@components/shell/GlobalNavSearch";
import { SearchField } from "@components/inputs/SearchField";
import { Alert } from "@/components/ui/alert";

export default function WorkspacesScreen() {
  return <WorkspacesIndexContent />;
}

function WorkspacesIndexContent() {
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();
  const setDefaultWorkspaceMutation = useSetDefaultWorkspaceMutation();
  const [pendingWorkspaceId, setPendingWorkspaceId] = useState<string | null>(null);
  const [setDefaultError, setSetDefaultError] = useState<string | null>(null);
  const normalizedPermissions = useMemo(
    () => (session.user.permissions ?? []).map((key) => key.toLowerCase()),
    [session.user.permissions],
  );
  const canCreateWorkspace =
    normalizedPermissions.includes("workspaces.create") ||
    normalizedPermissions.includes("workspaces.manage_all");
  const [searchQuery, setSearchQuery] = useState("");
  const workspacesPage = workspacesQuery.data;
  const workspaces: WorkspaceProfile[] = useMemo(
    () => workspacesPage?.items ?? [],
    [workspacesPage?.items],
  );
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
  const goToWorkspace = useCallback(
    (workspaceId: string) => navigate(getDefaultWorkspacePath(workspaceId)),
    [navigate],
  );

  const actions = canCreateWorkspace ? (
    <Button variant="primary" onClick={() => navigate("/workspaces/new")}>
      Create workspace
    </Button>
  ) : undefined;

  const handleWorkspaceSearchSubmit = useCallback((value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    const firstMatch = visibleWorkspaces[0];
    if (firstMatch) {
      goToWorkspace(firstMatch.id);
    }
  }, [visibleWorkspaces, goToWorkspace]);

  const handleResetSearch = useCallback(() => setSearchQuery(""), []);

  const handleSetDefaultWorkspace = useCallback(
    async (workspace: WorkspaceProfile) => {
      setSetDefaultError(null);
      setPendingWorkspaceId(workspace.id);
      try {
        await setDefaultWorkspaceMutation.mutateAsync(workspace.id);
        writePreferredWorkspaceId(workspace.id);
      } catch (error) {
        console.warn("workspaces.set_default.failed", error);
        setSetDefaultError("Unable to set the default workspace. Please try again.");
      } finally {
        setPendingWorkspaceId(null);
      }
    },
    [setDefaultWorkspaceMutation],
  );

  const topBarSearch = <GlobalNavSearch scope={{ kind: "directory" }} />;

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <PageState title="Loading workspaces" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
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
      <div className="space-y-6 rounded-2xl border border-border bg-card p-6 shadow-soft">
        <header>
          <h1 id="page-title" className="text-2xl font-semibold text-foreground">
            Workspaces
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Select a workspace to jump straight into documents.</p>
        </header>
        {setDefaultError ? (
          <Alert tone="danger" heading="We couldn't update your default workspace">
            {setDefaultError}
          </Alert>
        ) : null}
        <SearchField
          value={searchQuery}
          onValueChange={setSearchQuery}
          onSubmit={handleWorkspaceSearchSubmit}
          onClear={handleResetSearch}
          placeholder="Search workspaces by name or slug"
          className="w-full"
        />
        <section className="grid gap-5 lg:grid-cols-2">
          {visibleWorkspaces.map((workspace) => {
            const isUpdatingDefault =
              setDefaultWorkspaceMutation.isPending && pendingWorkspaceId === workspace.id;
            return (
              <div
                key={workspace.id}
                className="group relative rounded-xl border border-border bg-card p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background"
              >
                <button
                  type="button"
                  onClick={() => goToWorkspace(workspace.id)}
                  className="w-full text-left focus-visible:outline-none"
                  aria-label={`Open workspace ${workspace.name}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1 pr-24">
                      <h2 className="text-lg font-semibold text-foreground">{workspace.name}</h2>
                      <p className="text-sm text-muted-foreground">Slug: {workspace.slug}</p>
                    </div>
                  </div>
                  <p className="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">Permissions</p>
                  <p className="text-sm text-muted-foreground">
                    {workspace.permissions.length > 0 ? workspace.permissions.join(", ") : "None"}
                  </p>
                </button>
                <div className="absolute right-5 top-5">
                  {workspace.is_default ? (
                    <span className="rounded-full bg-muted px-2 py-1 text-xs font-semibold text-foreground">Default</span>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      isLoading={isUpdatingDefault}
                      disabled={isUpdatingDefault}
                      onClick={() => void handleSetDefaultWorkspace(workspace)}
                    >
                      Set as default
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      </div>
    );

  return (
    <WorkspaceDirectoryLayout
      actions={actions}
      search={topBarSearch}
      sidePanel={<DirectorySidebar canCreate={canCreateWorkspace} onCreate={() => navigate("/workspaces/new")} />}
    >
      {mainContent}
    </WorkspaceDirectoryLayout>
  );
}

function DirectorySidebar({ canCreate, onCreate }: { canCreate: boolean; onCreate: () => void }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-soft">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Workspace tips</p>
          <h2 className="text-sm font-semibold text-foreground">Why multiple workspaces?</h2>
        </header>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Segment teams by business unit or client, control access with roles, and tailor extraction settings per
          workspace. Everything stays organised and secure.
        </p>
        {canCreate ? (
          <Button variant="secondary" onClick={onCreate} className="w-full">
            New workspace
          </Button>
        ) : null}
      </section>
      <section className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-soft">
        <header className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Need a hand?</p>
          <h2 className="text-sm font-semibold text-foreground">Workspace setup checklist</h2>
        </header>
        <ul className="space-y-2 text-xs text-muted-foreground">
          <li>Add at least one additional administrator.</li>
          <li>Review configurations before uploading production files.</li>
          <li>Review workspace permissions for external collaborators.</li>
        </ul>
      </section>
    </div>
  );
}


function EmptyStateCreate({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="mx-auto max-w-3xl rounded-2xl border border-dashed border-border bg-card p-10 text-center shadow-soft">
      <h1 id="page-title" className="text-2xl font-semibold text-foreground">No workspaces yet</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Create your first workspace to start uploading configuration sets and documents.
      </p>
      <Button variant="primary" onClick={onCreate} className="mt-6">
        Create workspace
      </Button>
    </div>
  );
}
