import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { Select } from "@ui/Select";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import { useConfigurationsQuery, useCreateConfigurationMutation } from "@shared/configurations";
import { createScopedStorage } from "@shared/storage";

const TEMPLATE_OPTIONS = [{ value: "default", label: "Default template" }] as const;

const buildStorageKey = (workspaceId: string) => `ade.ui.workspace.${workspaceId}.config-builder.last`;
const buildConfigDetailPath = (workspaceId: string, configId: string) =>
  `/workspaces/${workspaceId}/config-builder/${encodeURIComponent(configId)}`;

type LastSelection = { readonly configId?: string | null } | null;

export const handle = { workspaceSectionId: "config-builder" } as const;

export default function WorkspaceConfigsIndexRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const storage = useMemo(() => createScopedStorage(buildStorageKey(workspace.id)), [workspace.id]);
  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const createConfig = useCreateConfigurationMutation(workspace.id);

  const [displayName, setDisplayName] = useState(() => `${workspace.name} Config`);
  const [templateId, setTemplateId] = useState<string>(TEMPLATE_OPTIONS[0]?.value ?? "default");
  const [validationError, setValidationError] = useState<string | null>(null);

  const configurations = useMemo(
    () =>
      (configurationsQuery.data?.items ?? []).filter(
        (config) => !("deleted_at" in config && (config as { deleted_at?: string | null }).deleted_at),
      ),
    [configurationsQuery.data],
  );
  const lastSelection = useMemo(() => storage.get<LastSelection>(), [storage]);

  const handleOpenConfig = (configId: string) => {
    storage.set<LastSelection>({ configId });
    navigate(buildConfigDetailPath(workspace.id, configId));
  };

  const handleOpenEditor = (configId: string) => {
    storage.set<LastSelection>({ configId });
    navigate(`${buildConfigDetailPath(workspace.id, configId)}/editor`);
  };

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = displayName.trim();
    if (!trimmed) {
      setValidationError("Enter a display name for the configuration.");
      return;
    }
    setValidationError(null);
    createConfig.mutate(
      {
        displayName: trimmed,
        source: { type: "template", templateId },
      },
      {
        onSuccess(record) {
          storage.set<LastSelection>({ configId: record.id });
          navigate(buildConfigDetailPath(workspace.id, record.id));
        },
      },
    );
  };

  const creationError = validationError ?? (createConfig.error instanceof Error ? createConfig.error.message : null);
  const canSubmit = displayName.trim().length > 0 && !createConfig.isPending;

  if (configurationsQuery.isLoading) {
    return <PageState variant="loading" title="Loading configurations" description="Fetching workspace configurations…" />;
  }

  if (configurationsQuery.isError) {
    return <PageState variant="error" title="Unable to load configurations" description="Try refreshing the page." />;
  }

  if (configurations.length === 0) {
    return (
      <PageState
        className="mx-auto w-full max-w-xl"
        title="Create your first configuration"
        description="Copy a starter template into this workspace to begin editing detectors, hooks, and manifests."
        action={
          <form onSubmit={handleCreate} className="space-y-4 text-left">
            <FormField label="Configuration name" required>
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Membership normalization"
                disabled={createConfig.isPending}
                autoFocus
              />
            </FormField>
            <FormField label="Template">
              <Select
                value={templateId}
                onChange={(event) => setTemplateId(event.target.value)}
                disabled={createConfig.isPending}
              >
                {TEMPLATE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </FormField>
            {creationError ? <p className="text-sm font-medium text-danger-600">{creationError}</p> : null}
            <Button type="submit" className="w-full" disabled={!canSubmit} isLoading={createConfig.isPending}>
              Create from template
            </Button>
          </form>
        }
      />
    );
  }

  return (
    <div className="grid gap-6 p-4 lg:grid-cols-[minmax(0,2fr),minmax(0,1fr)]">
      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Configurations</h1>
            <p className="text-sm text-slate-500">
              Open an existing configuration to view manifest summaries, run validation, or launch the editor.
            </p>
          </div>
          {lastSelection?.configId ? (
            <Button variant="ghost" size="sm" onClick={() => handleOpenConfig(lastSelection.configId!)}>
              Resume last opened
            </Button>
          ) : null}
        </header>
        <div className="divide-y divide-slate-200 rounded-xl border border-slate-200">
          {configurations.map((config) => (
            <article key={config.id} className="grid gap-3 p-4 md:grid-cols-[minmax(0,2fr),auto] md:items-center">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold text-slate-900">{config.display_name}</h2>
                  <StatusPill status={config.status} />
                  {lastSelection?.configId === config.id ? (
                    <span className="text-xs font-medium uppercase tracking-wide text-brand-600">Last opened</span>
                  ) : null}
                </div>
                <p className="text-sm text-slate-500">
                  Updated {new Date(config.updated_at).toLocaleString()} · Active version{" "}
                  {("active_version" in config ? (config as { active_version?: number | null }).active_version : null) ??
                    config.configuration_version ??
                    "—"}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <Button size="sm" variant="secondary" onClick={() => handleOpenConfig(config.id)}>
                  View details
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleOpenEditor(config.id)}>
                  Open editor
                </Button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <aside className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-slate-900">New configuration</h2>
          <p className="text-sm text-slate-500">Copy the starter template to begin editing detectors, hooks, and manifests.</p>
        </div>
        <form onSubmit={handleCreate} className="space-y-4">
          <FormField label="Configuration name" required>
            <Input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Membership normalization"
              disabled={createConfig.isPending}
            />
          </FormField>
          <FormField label="Template">
            <Select
              value={templateId}
              onChange={(event) => setTemplateId(event.target.value)}
              disabled={createConfig.isPending}
            >
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </FormField>
          {creationError ? <p className="text-sm font-medium text-danger-600">{creationError}</p> : null}
          <Button type="submit" className="w-full" disabled={!canSubmit} isLoading={createConfig.isPending}>
            Create from template
          </Button>
        </form>
      </aside>
    </div>
  );
}

function StatusPill({ status }: { readonly status: string }) {
  const normalized = status.toLowerCase();
  const styles =
    normalized === "active"
      ? "bg-emerald-100 text-emerald-700"
      : normalized === "draft"
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-200 text-slate-700";
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${styles}`}>{status}</span>;
}
