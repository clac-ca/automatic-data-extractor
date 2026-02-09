import { useMemo } from "react";
import { parseAsInteger, parseAsString, useQueryState } from "nuqs";

import { generatePath, Link, useNavigate } from "react-router-dom";
import { ArrowRight, Plus } from "lucide-react";

import { useConfigureAuthenticatedTopbar } from "@/app/layouts/components/topbar/AuthenticatedTopbarContext";
import { useSession } from "@/providers/auth/SessionContext";
import { useWorkspacesQuery } from "@/hooks/workspaces";
import type { WorkspaceProfile } from "@/types/workspaces";
import { Button } from "@/components/ui/button";
import { PageState } from "@/components/layout";
import {
  WorkspacesTopbarSearch,
  WorkspacesTopbarSearchButton,
} from "@/pages/Workspaces/components/WorkspacesTopbarSearch";

export default function WorkspacesScreen() {
  return <WorkspacesIndexContent />;
}

const WORKSPACE_PAGE_SIZE = 25;
const WORKSPACE_SORT = JSON.stringify([{ id: "name", desc: false }]);

function WorkspacesIndexContent() {
  const navigate = useNavigate();
  const session = useSession();

  const topbarConfig = useMemo(
    () => ({
      desktopCenter: <WorkspacesTopbarSearch className="w-full max-w-xl" />,
      mobileAction: <WorkspacesTopbarSearchButton />,
    }),
    [],
  );
  useConfigureAuthenticatedTopbar(topbarConfig);

  const normalizedPermissions = useMemo(
    () => (session.user.permissions ?? []).map((key) => key.toLowerCase()),
    [session.user.permissions],
  );
  const canCreateWorkspace =
    normalizedPermissions.includes("workspaces.create") ||
    normalizedPermissions.includes("workspaces.manage_all");
  const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
  const [searchValue, setSearchValue] = useQueryState("q", parseAsString);
  const searchQuery = (searchValue ?? "").trim();
  const workspacesQuery = useWorkspacesQuery({
    page,
    pageSize: WORKSPACE_PAGE_SIZE,
    sort: WORKSPACE_SORT,
    q: searchQuery.length > 0 ? searchQuery : null,
    includeTotal: true,
  });
  const workspacesPage = workspacesQuery.data;
  const workspaces: WorkspaceProfile[] = useMemo(
    () => workspacesPage?.items ?? [],
    [workspacesPage?.items],
  );
  const totalCount =
    typeof workspacesPage?.meta.totalCount === "number" ? workspacesPage.meta.totalCount : workspaces.length;
  const pageCount = Math.max(1, Math.ceil(totalCount / WORKSPACE_PAGE_SIZE));
  const canPreviousPage = page > 1;
  const canNextPage = page < pageCount;

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-full items-center justify-center bg-background px-6">
        <PageState title="Loading workspaces" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-full items-center justify-center bg-background px-6">
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

  const handlePreviousPage = () => {
    if (!canPreviousPage) {
      return;
    }
    void setPage(page - 1);
  };

  const handleNextPage = () => {
    if (!canNextPage) {
      return;
    }
    void setPage(page + 1);
  };

  const clearSearch = () => {
    if (page > 1) {
      void setPage(1);
    }
    void setSearchValue(null);
  };

  const mainContent =
    workspaces.length === 0 && searchQuery.length > 0 ? (
      <PageState
        title="No workspaces found"
        description="Try a different name or slug."
        action={
          <Button variant="secondary" onClick={clearSearch}>
            Clear search
          </Button>
        }
      />
    ) : workspaces.length === 0 ? (
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
    ) : (
      <div className="space-y-5 rounded-2xl border border-border bg-card p-6 shadow-soft">
        <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 id="page-title" className="text-2xl font-semibold text-foreground">
              Workspaces
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Select a workspace to jump straight into documents.
            </p>
          </div>
          {canCreateWorkspace ? (
            <Button onClick={() => navigate("/workspaces/new")} className="w-full md:w-auto">
              <Plus className="size-4" />
              New workspace
            </Button>
          ) : null}
        </header>

        <ul className="overflow-hidden rounded-xl border border-border divide-y divide-border">
          {workspaces.map((workspace) => {
            const workspacePath = generatePath("/workspaces/:workspaceId/documents", {
              workspaceId: workspace.id,
            });

            return (
              <li
                key={workspace.id}
                className="bg-background transition-colors hover:bg-muted/30"
              >
                <Link
                  to={workspacePath}
                  aria-label={`Open workspace ${workspace.name}`}
                  className="group flex items-center justify-between gap-4 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                >
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold text-foreground">{workspace.name}</h2>
                    <p className="mt-0.5 text-sm text-muted-foreground">Slug: {workspace.slug}</p>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                </Link>
              </li>
            );
          })}
        </ul>

        {pageCount > 1 ? (
          <div className="flex items-center justify-between gap-3">
            <Button variant="outline" size="sm" onClick={handlePreviousPage} disabled={!canPreviousPage}>
              Previous
            </Button>
            <p className="text-sm text-muted-foreground">
              Page {page} of {pageCount}
            </p>
            <Button variant="outline" size="sm" onClick={handleNextPage} disabled={!canNextPage}>
              Next
            </Button>
          </div>
        ) : null}
      </div>
    );

  return <div className="mx-auto w-full max-w-6xl px-4 py-8">{mainContent}</div>;
}

function EmptyStateCreate({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="mx-auto max-w-3xl rounded-2xl border border-dashed border-border bg-card p-10 text-center shadow-soft">
      <h1 id="page-title" className="text-2xl font-semibold text-foreground">
        No workspaces yet
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Create your first workspace to start uploading configuration sets and documents.
      </p>
      <Button onClick={onCreate} className="mt-6">
        <Plus className="size-4" />
        Create workspace
      </Button>
    </div>
  );
}
