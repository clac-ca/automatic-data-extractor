import { useMemo } from "react";
import type { ReactNode } from "react";

import { Button } from "../../ui";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { trackEvent } from "../../shared/telemetry/events";

interface ConfigurationSummary {
  readonly id: string;
  readonly title: string;
  readonly status: "draft" | "published" | "archived";
  readonly lastRunAt: string;
  readonly successRate7d: number;
  readonly pendingJobs: number;
  readonly version: string;
  readonly publishedBy: string;
  readonly publishedAt: string;
  readonly notes: string;
}

// TODO: replace with real API call once configuration endpoints are available.
const placeholderConfiguration: ConfigurationSummary = {
  id: "config-001",
  title: "Invoice extraction rules",
  status: "published",
  lastRunAt: new Date().toISOString(),
  successRate7d: 0.92,
  pendingJobs: 3,
  version: "v12",
  publishedBy: "Dana Operator",
  publishedAt: new Date(Date.now() - 86_400_000).toISOString(),
  notes: "Latest revision adds support for multi-line descriptions and VAT parsing.",
};

export function ConfigurationsRoute() {
  const { openInspector } = useWorkspaceChrome();
  const configuration = placeholderConfiguration;

  const statusBadge = useMemo(() => {
    switch (configuration.status) {
      case "published":
        return { label: "Published", className: "bg-success-50 text-success-700" };
      case "draft":
        return { label: "Draft", className: "bg-warning-50 text-warning-700" };
      case "archived":
      default:
        return { label: "Archived", className: "bg-slate-200 text-slate-700" };
    }
  }, [configuration.status]);

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 id="page-title" className="text-2xl font-semibold text-slate-900">
            {configuration.title}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage extraction rules, deployment status, and revision history.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            onClick={() => {
              trackEvent({ name: "configurations.inspect", payload: { configurationId: configuration.id } });
              openInspector({
                title: configuration.title,
                content: <ConfigurationInspector configuration={configuration} />,
              });
            }}
          >
            Review configuration
          </Button>
          <Button variant="ghost">View history</Button>
        </div>
      </header>

      <section className="grid gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 md:grid-cols-3">
        <StatusTile
          label="Last run"
          value={formatTimestamp(configuration.lastRunAt)}
          details={`${Math.round(configuration.successRate7d * 100)}% success (7d)`}
        />
        <StatusTile label="Pending jobs" value={configuration.pendingJobs.toString()} details="Awaiting processing" />
        <StatusTile label="Status" value={statusBadge.label} badgeClassName={statusBadge.className} />
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h2 className="text-sm font-semibold text-slate-800">Deployment summary</h2>
          <dl className="space-y-2 text-sm text-slate-600">
            <InfoRow label="Version">{configuration.version}</InfoRow>
            <InfoRow label="Published by">{configuration.publishedBy}</InfoRow>
            <InfoRow label="Published at">{formatTimestamp(configuration.publishedAt)}</InfoRow>
          </dl>
        </div>
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h2 className="text-sm font-semibold text-slate-800">Notes</h2>
          <p className="text-sm leading-relaxed text-slate-600">{configuration.notes}</p>
        </div>
      </section>
    </section>
  );
}

function StatusTile({
  label,
  value,
  details,
  badgeClassName,
}: {
  readonly label: string;
  readonly value: string;
  readonly details?: string;
  readonly badgeClassName?: string;
}) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-soft">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">
        {badgeClassName ? (
          <span className={`inline-flex items-center rounded-full px-2 py-1 text-sm font-semibold ${badgeClassName}`}>
            {value}
          </span>
        ) : (
          value
        )}
      </p>
      {details ? <p className="mt-2 text-xs text-slate-500">{details}</p> : null}
    </div>
  );
}

function InfoRow({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-700">{children}</dd>
    </div>
  );
}

function ConfigurationInspector({
  configuration,
}: {
  readonly configuration: ConfigurationSummary;
}) {
  return (
    <div className="space-y-6 text-sm text-slate-600">
      <section className="space-y-2">
        <h3 className="text-base font-semibold text-slate-900">Version details</h3>
        <dl className="space-y-2">
          <InfoRow label="Version">{configuration.version}</InfoRow>
          <InfoRow label="Published by">{configuration.publishedBy}</InfoRow>
          <InfoRow label="Published at">{formatTimestamp(configuration.publishedAt)}</InfoRow>
        </dl>
      </section>
      <section className="space-y-2">
        <h3 className="text-base font-semibold text-slate-900">Change log</h3>
        <p className="leading-relaxed">{configuration.notes}</p>
      </section>
      <section className="space-y-2">
        <h3 className="text-base font-semibold text-slate-900">Next steps</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>Validate sample documents against the new schema.</li>
          <li>Communicate changes to downstream reviewers.</li>
        </ul>
      </section>
    </div>
  );
}

function formatTimestamp(timestamp: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(timestamp));
  } catch {
    return timestamp;
  }
}
