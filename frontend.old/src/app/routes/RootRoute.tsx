import { Link } from "react-router-dom";

import { useWorkspacesQuery } from "../../features/workspaces/hooks/useWorkspacesQuery";
import { Button } from "../../ui";
import { PageState } from "../components/PageState";

export function RootRoute() {
  const workspacesQuery = useWorkspacesQuery();
  const workspaces = workspacesQuery.data ?? [];
  const defaultWorkspace = workspaces.find((workspace) => workspace.is_default) ?? workspaces[0];

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-[320px] items-center justify-center">
        <PageState title="Loading workspace overview" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <PageState
        title="We couldn't load your workspaces"
        description="Refresh the page or try again later. If the problem persists, contact support."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => workspacesQuery.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  const buttonLinkClass =
    "inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white";

  return (
    <div className="space-y-8">
      <section className="rounded-xl bg-gradient-to-r from-brand-600 via-brand-500 to-brand-600 px-8 py-10 text-white shadow-soft">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <p className="text-sm uppercase tracking-wide text-white/70">
              Welcome back
            </p>
            <h1 className="text-3xl font-semibold leading-tight">Operator home</h1>
            <p className="max-w-xl text-sm text-white/80">
              Keep an eye on workspace health, jump into recent activity, and monitor extraction jobs
              from a single view.
            </p>
          </div>
          <div className="flex gap-3 text-sm font-semibold">
            <Link
              to="/workspaces"
              className="rounded-lg bg-white/10 px-4 py-2 transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
            >
              View all workspaces
            </Link>
            <Link
              to="/documents"
              className="rounded-lg bg-white px-4 py-2 text-brand-600 transition hover:bg-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
            >
              Upload documents
            </Link>
          </div>
        </div>
      </section>

      {workspaces.length === 0 ? (
        <PageState
          title="No workspaces yet"
          description="Create your first workspace to start uploading configuration sets and documents."
          action={
            <Link to="/workspaces" className={buttonLinkClass}>
              Create workspace
            </Link>
          }
        />
      ) : (
        <section className="grid gap-6 md:grid-cols-2">
          <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-soft">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Workspace summary
            </p>
            <h2 className="mt-2 text-xl font-semibold text-slate-900">
              {workspaces.length} workspace{workspaces.length === 1 ? "" : "s"}
            </h2>
            {defaultWorkspace ? (
              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">Preferred workspace</p>
                <p className="text-base font-semibold text-slate-900">{defaultWorkspace.name}</p>
                <p className="text-xs text-slate-500">{defaultWorkspace.slug}</p>
              </div>
            ) : null}
            <Link to="/workspaces" className={`mt-4 ${buttonLinkClass}`}>
              Manage workspaces
            </Link>
          </article>

          <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-soft">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Quick actions
            </p>
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              <li>
                <Link className="font-semibold text-brand-600 hover:text-brand-700" to="/documents">
                  Upload new documents
                </Link>{" "}
                to kick off extraction jobs.
              </li>
              <li>
                <Link className="font-semibold text-brand-600 hover:text-brand-700" to="/jobs">
                  View job history
                </Link>{" "}
                to track recent runs.
              </li>
              <li>
                <Link className="font-semibold text-brand-600 hover:text-brand-700" to="/settings">
                  Review platform settings
                </Link>{" "}
                to confirm configuration defaults.
              </li>
            </ul>
          </article>
        </section>
      )}
    </div>
  );
}
