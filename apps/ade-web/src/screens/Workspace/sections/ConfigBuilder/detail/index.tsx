import { useMemo } from "react";

import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";

import { useConfigurationsQuery } from "@shared/configurations";

interface WorkspaceConfigRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function WorkspaceConfigRoute({ params }: WorkspaceConfigRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const configId = params?.configId;

  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });

  const config = useMemo(
    () => configurationsQuery.data?.items.find((item) => item.id === configId),
    [configurationsQuery.data, configId],
  );

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="Pick a configuration from the list to view its details."
      />
    );
  }

  if (configurationsQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration"
        description="Fetching configuration details."
      />
    );
  }

  if (!config) {
    return (
      <PageState
        variant="error"
        title="Configuration unavailable"
        description="The selected configuration could not be found. It may have been deleted."
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Configuration</p>
            <h1 className="text-xl font-semibold text-slate-900">{config.display_name}</h1>
          </div>
          <Button
            variant="secondary"
            onClick={() =>
              navigate(`/workspaces/${workspace.id}/config-builder/${encodeURIComponent(config.id)}/editor`)
            }
          >
            Open editor
          </Button>
        </header>
        <dl className="grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Config ID</dt>
            <dd className="text-sm text-slate-700">{config.id}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</dt>
            <dd className="text-sm capitalize text-slate-700">{config.status.toLowerCase()}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Updated</dt>
            <dd className="text-sm text-slate-700">{new Date(config.updated_at).toLocaleString()}</dd>
          </div>
        </dl>
      </section>
      <section className="flex-1 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6">
        <h2 className="text-base font-semibold text-slate-800">Overview</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          The refreshed config workbench will eventually surface manifest summaries, validation history, and deployment metrics
          here. For now this page offers a quick launch point into the editor while we rebuild the experience.
        </p>
      </section>
    </div>
  );
}
