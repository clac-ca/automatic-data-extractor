import { useOutletContext, useParams } from "react-router-dom";

import { useDocumentTypeQuery } from "../hooks/useDocumentTypeQuery";
import { formatDateTime } from "../../../shared/dates";
import type { WorkspaceProfile } from "../../../shared/api/types";

interface WorkspaceOutletContext {
  workspace?: WorkspaceProfile;
}

export function DocumentTypeRoute() {
  const params = useParams<{ workspaceId: string; documentTypeId: string }>();
  const { workspace } = useOutletContext<WorkspaceOutletContext>();

  const workspaceId = params.workspaceId ?? workspace?.id;
  const documentTypeId = params.documentTypeId;

  if (!workspaceId || !documentTypeId) {
    return (
      <div className="rounded border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
        Select a document type to view its details.
      </div>
    );
  }

  const {
    data,
    isLoading,
    error,
  } = useDocumentTypeQuery(workspaceId, documentTypeId);

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-300">
        Loading document type…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-200">
        We were unable to load this document type.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="rounded border border-slate-800 bg-slate-900/60 p-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-slate-100">{data.display_name}</h2>
            <p className="text-sm text-slate-400">Workspace {workspace?.name ?? workspaceId}</p>
          </div>
        </header>
        <dl className="mt-6 grid gap-6 md:grid-cols-3">
          <Stat label="Last run" value={formatDateTime(data.last_run_at)} />
          <Stat
            label="Success rate (7d)"
            value={data.success_rate_7d !== null ? `${Math.round(data.success_rate_7d * 100)}%` : "—"}
          />
          <Stat label="Pending jobs" value={data.pending_jobs.toString()} />
        </dl>
      </section>
      {data.alerts && data.alerts.length > 0 && (
        <section className="space-y-3 rounded border border-rose-500/40 bg-rose-500/10 p-6">
          <h3 className="text-sm font-semibold text-rose-200">Active alerts</h3>
          <ul className="space-y-2 text-sm text-rose-100">
            {data.alerts.map((alert, index) => (
              <li key={index} className="rounded border border-rose-500/20 bg-rose-500/10 px-3 py-2">
                {alert}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="space-y-4 rounded border border-slate-800 bg-slate-900/60 p-6">
        <h3 className="text-lg font-semibold text-slate-100">Configuration</h3>
        <dl className="grid gap-4 text-sm text-slate-300 md:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Version</dt>
            <dd className="mt-1">v{data.configuration_summary.version}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Published by</dt>
            <dd className="mt-1">{data.configuration_summary.published_by}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Published at</dt>
            <dd className="mt-1">{formatDateTime(data.configuration_summary.published_at)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
            <dd className="mt-1">{data.configuration_summary.draft ? "Draft" : "Published"}</dd>
          </div>
        </dl>
        {data.configuration_summary.description && (
          <p className="text-sm text-slate-300">{data.configuration_summary.description}</p>
        )}
        {data.configuration_summary.inputs && data.configuration_summary.inputs.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-slate-200">Inputs</h4>
            <ul className="space-y-2 text-sm text-slate-300">
              {data.configuration_summary.inputs.map((input) => (
                <li key={input.name} className="rounded border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <p className="font-medium text-slate-100">{input.name}</p>
                  <p className="text-xs text-slate-500">
                    {input.type} • {input.required ? "Required" : "Optional"}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.configuration_summary.revision_notes && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-slate-200">Revision notes</h4>
            <p className="text-sm text-slate-300">{data.configuration_summary.revision_notes}</p>
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 p-4">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-2 text-lg font-semibold text-slate-100">{value}</dd>
    </div>
  );
}
