import { useEffect, useMemo } from "react";
import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";

import { useConfigurationQuery } from "@shared/configurations";
import { createLastSelectionStorage, persistLastSelection } from "../storage";

interface WorkspaceConfigRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function WorkspaceConfigRoute({ params }: WorkspaceConfigRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const configId = params?.configId;
  const lastSelectionStorage = useMemo(() => createLastSelectionStorage(workspace.id), [workspace.id]);

  const configQuery = useConfigurationQuery({ workspaceId: workspace.id, configurationId: configId });
  const config = configQuery.data;

  useEffect(() => {
    if (!configId || !config) {
      return;
    }
    persistLastSelection(lastSelectionStorage, configId);
  }, [configId, config, lastSelectionStorage]);

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="Pick a configuration from the list to view its details."
      />
    );
  }

  if (configQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration"
        description="Fetching configuration details."
      />
    );
  }

  if (configQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration"
        description="Try refreshing the page."
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
            <dd className="text-sm text-slate-700">{formatTimestamp(config.updated_at)}</dd>
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

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
