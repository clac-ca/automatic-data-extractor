import { useMemo } from "react";

import type { ConfigurationSummary } from "../../../shared/api/types";
import { RightDrawer } from "../../../shared/chrome";
import { formatDateTime } from "../../../shared/dates";
import { useDocumentTypeDetail } from "./DocumentTypeDetailContext";

export function DocumentTypeDetailView() {
  const {
    documentType,
    workspaceName,
    isConfigurationDrawerOpen,
    openConfigurationDrawer,
    closeConfigurationDrawer,
  } = useDocumentTypeDetail();

  const metrics = useMemo(
    () => [
      {
        id: "last-run",
        label: "Last run",
        value: formatDateTime(documentType.last_run_at),
      },
      {
        id: "success-rate",
        label: "Success rate (7d)",
        value: formatSuccessRate(documentType.success_rate_7d),
      },
      {
        id: "pending-jobs",
        label: "Pending jobs",
        value: documentType.pending_jobs.toString(),
      },
    ],
    [documentType.last_run_at, documentType.success_rate_7d, documentType.pending_jobs],
  );

  const alerts = documentType.alerts ?? [];

  return (
    <>
      <div className="space-y-8">
        <section className="space-y-6 rounded border border-slate-800 bg-slate-900/60 p-6">
          <DocumentTypeSummaryHeader
            workspaceName={workspaceName}
            status={documentType.status}
            displayName={documentType.display_name}
            onOpenConfiguration={openConfigurationDrawer}
          />
          <DocumentTypeStatusStrip metrics={metrics} />
        </section>
        {alerts.length > 0 ? <DocumentTypeAlertsPanel alerts={alerts} /> : null}
        <DocumentTypeConfigurationSection
          summary={documentType.configuration_summary}
          onOpenDrawer={openConfigurationDrawer}
        />
      </div>
      <RightDrawer
        open={isConfigurationDrawerOpen}
        onClose={closeConfigurationDrawer}
        title="Configuration details"
        description="Review the currently active configuration before publishing updates."
      >
        <DocumentTypeConfigurationDetails summary={documentType.configuration_summary} />
      </RightDrawer>
    </>
  );
}

interface DocumentTypeMetric {
  id: string;
  label: string;
  value: string;
}

function DocumentTypeSummaryHeader({
  workspaceName,
  status,
  displayName,
  onOpenConfiguration,
}: {
  workspaceName: string;
  status: string;
  displayName: string;
  onOpenConfiguration: () => void;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-semibold text-slate-100">{displayName}</h2>
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${getStatusStyles(status)}`}>
            {formatStatus(status)}
          </span>
        </div>
        <p className="text-sm text-slate-400">Workspace {workspaceName}</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenConfiguration}
          className="inline-flex items-center gap-2 rounded border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-sky-500 hover:text-sky-200"
        >
          Review configuration details
        </button>
      </div>
    </header>
  );
}

function DocumentTypeStatusStrip({ metrics }: { metrics: DocumentTypeMetric[] }) {
  return (
    <dl className="grid gap-6 md:grid-cols-3">
      {metrics.map((metric) => (
        <div key={metric.id} className="rounded border border-slate-800 bg-slate-950/80 p-4">
          <dt className="text-xs uppercase tracking-wide text-slate-500">{metric.label}</dt>
          <dd className="mt-2 text-lg font-semibold text-slate-100">{metric.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function DocumentTypeAlertsPanel({ alerts }: { alerts: string[] }) {
  return (
    <section className="space-y-3 rounded border border-rose-500/40 bg-rose-500/10 p-6">
      <h3 className="text-sm font-semibold text-rose-200">Active alerts</h3>
      <ul className="space-y-2 text-sm text-rose-100">
        {alerts.map((alert, index) => (
          <li key={index} className="rounded border border-rose-500/20 bg-rose-500/10 px-3 py-2">
            {alert}
          </li>
        ))}
      </ul>
    </section>
  );
}

function DocumentTypeConfigurationSection({
  summary,
  onOpenDrawer,
}: {
  summary: ConfigurationSummary;
  onOpenDrawer: () => void;
}) {
  return (
    <section className="space-y-5 rounded border border-slate-800 bg-slate-900/60 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-slate-100">Configuration</h3>
          <p className="text-sm text-slate-400">This configuration powers document ingestion for the selected type.</p>
        </div>
        <button
          type="button"
          onClick={onOpenDrawer}
          className="inline-flex items-center gap-2 rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
        >
          View full configuration
        </button>
      </div>
      <dl className="grid gap-4 text-sm text-slate-300 md:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Version</dt>
          <dd className="mt-1">v{summary.version}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Published by</dt>
          <dd className="mt-1">{summary.published_by}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Published at</dt>
          <dd className="mt-1">{formatDateTime(summary.published_at)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
          <dd className="mt-1">{summary.draft ? "Draft" : "Published"}</dd>
        </div>
      </dl>
      {summary.description ? <p className="text-sm text-slate-300">{summary.description}</p> : null}
    </section>
  );
}

function DocumentTypeConfigurationDetails({ summary }: { summary: ConfigurationSummary }) {
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Snapshot</h3>
        <dl className="grid gap-4 md:grid-cols-2">
          <Detail label="Version" value={`v${summary.version}`} />
          <Detail label="Published by" value={summary.published_by} />
          <Detail label="Published at" value={formatDateTime(summary.published_at)} />
          <Detail label="Status" value={summary.draft ? "Draft" : "Published"} />
        </dl>
      </section>
      {summary.description ? (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Description</h3>
          <p className="text-sm text-slate-200">{summary.description}</p>
        </section>
      ) : null}
      {summary.inputs && summary.inputs.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Inputs</h3>
          <ul className="space-y-2">
            {summary.inputs.map((input) => (
              <li key={input.name} className="rounded border border-slate-800 bg-slate-950/80 px-3 py-2">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-100">{input.name}</p>
                  <span className="text-xs uppercase tracking-wide text-slate-500">{input.required ? "Required" : "Optional"}</span>
                </div>
                <p className="text-xs text-slate-400">{input.type}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {summary.revision_notes ? (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Revision notes</h3>
          <p className="text-sm text-slate-200">{summary.revision_notes}</p>
        </section>
      ) : null}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-200">{value}</dd>
    </div>
  );
}

const STATUS_STYLES: Record<string, string> = {
  active: "border-emerald-400/40 bg-emerald-500/20 text-emerald-100",
  paused: "border-amber-400/40 bg-amber-500/20 text-amber-100",
  error: "border-rose-400/40 bg-rose-500/20 text-rose-100",
};

function getStatusStyles(status: string) {
  const key = status.toLowerCase();
  return STATUS_STYLES[key] ?? "border-slate-700 bg-slate-800/80 text-slate-200";
}

function formatStatus(status: string) {
  return status
    .toLowerCase()
    .split(/[_\s]+/)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function formatSuccessRate(rate: number | null) {
  if (rate === null || Number.isNaN(rate)) {
    return "—";
  }

  return `${Math.round(rate * 100)}%`;
}
