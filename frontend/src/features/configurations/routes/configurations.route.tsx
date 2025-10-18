import { useEffect, useMemo, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { Alert } from "../../../ui/alert";
import { Button } from "../../../ui/button";
import { useWorkspaceContext } from "../../workspaces/context/WorkspaceContext";
import { useConfigurationsQuery } from "../hooks/useConfigurationsQuery";
import { useCreateConfigurationMutation } from "../hooks/useCreateConfigurationMutation";
import { useActivateConfigurationMutation } from "../hooks/useActivateConfigurationMutation";
import { ConfigurationSidebar } from "../components/ConfigurationSidebar";
import { ConfigurationColumnsEditor } from "../components/ConfigurationColumnsEditor";
import { ConfigurationScriptPanel } from "../components/ConfigurationScriptPanel";
import type { ConfigurationRecord } from "../../../shared/types/configurations";

const VIEW_OPTIONS = [
  { id: "columns", label: "Columns" },
  { id: "scripts", label: "Scripts" },
] as const;

export function ConfigurationsRoute() {
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    // eslint-disable-next-line no-console
    console.debug("[ConfigurationsRoute] mount");
    return () => {
      // eslint-disable-next-line no-console
      console.debug("[ConfigurationsRoute] unmount");
    };
  }, []);
  const { workspace } = useWorkspaceContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const viewParam = (searchParams.get("view") as typeof VIEW_OPTIONS[number]["id"]) ?? "columns";
  const requestedConfigurationId = searchParams.get("configurationId");
  const requestedColumn = searchParams.get("column");
  const requestedScriptVersionId = searchParams.get("scriptVersionId");

  const {
    data: configurations,
    isLoading,
    isError,
  } = useConfigurationsQuery(workspace.id);

  const selectedConfiguration = useMemo(() => {
    if (!configurations || configurations.length === 0) {
      return null;
    }
    const byId = configurations.find((config) => config.configuration_id === requestedConfigurationId);
    if (byId) {
      return byId;
    }
    const active = configurations.find((config) => config.is_active);
    return active ?? configurations[0];
  }, [configurations, requestedConfigurationId]);

  useEffect(() => {
    if (selectedConfiguration && requestedConfigurationId !== selectedConfiguration.configuration_id) {
      const next = new URLSearchParams(searchParams);
      next.set("configurationId", selectedConfiguration.configuration_id);
      if (!next.has("view")) {
        next.set("view", "columns");
      }
      setSearchParams(next, { replace: true });
    }
  }, [requestedConfigurationId, searchParams, selectedConfiguration, setSearchParams]);

  const createMutation = useCreateConfigurationMutation(workspace.id);
  const activateMutation = useActivateConfigurationMutation(workspace.id);

  const handleSelectConfiguration = (configurationId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("configurationId", configurationId);
    if (!next.has("view")) {
      next.set("view", "columns");
    }
    next.delete("column");
    next.delete("scriptVersionId");
    setSearchParams(next, { replace: true });
  };

  const handleChangeView = (nextView: typeof VIEW_OPTIONS[number]["id"]) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", nextView);
    if (nextView !== "scripts") {
      next.delete("column");
      next.delete("scriptVersionId");
    }
    setSearchParams(next, { replace: true });
  };

  const handleManageScript = (canonicalKey: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", "scripts");
    next.set("column", canonicalKey);
    next.delete("scriptVersionId");
    setSearchParams(next, { replace: true });
  };

  const handleSelectScriptVersion = (scriptVersionId: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (scriptVersionId) {
      next.set("scriptVersionId", scriptVersionId);
    } else {
      next.delete("scriptVersionId");
    }
    setSearchParams(next, { replace: true });
  };

  const handleCreateFromActive = async () => {
    if (createMutation.isPending) {
      return;
    }
    const title = buildDraftTitle(configurations, "Copy of active configuration");
    try {
      const result = await createMutation.mutateAsync({
        title,
        clone_from_active: true,
        payload: {},
      });
      handleSelectConfiguration(result.configuration_id);
      handleChangeView("columns");
    } catch (error) {
      console.error("Failed to create configuration from active", error);
    }
  };

  const handleCreateBlank = async () => {
    if (createMutation.isPending) {
      return;
    }
    const title = buildDraftTitle(configurations, "New configuration");
    try {
      const result = await createMutation.mutateAsync({
        title,
        payload: {},
      });
      handleSelectConfiguration(result.configuration_id);
      handleChangeView("columns");
    } catch (error) {
      console.error("Failed to create configuration", error);
    }
  };

  const handleActivate = async (configurationId: string) => {
    if (activateMutation.isPending) {
      return;
    }
    const confirmed = window.confirm("Activate this configuration? This will replace the current active version.");
    if (!confirmed) {
      return;
    }
    try {
      await activateMutation.mutateAsync(configurationId);
    } catch (error) {
      console.error("Failed to activate configuration", error);
    }
  };

  return (
    <div className="space-y-6">
      {isError ? (
        <Alert tone="danger" heading="Unable to load configurations">
          Please refresh the page or try again later.
        </Alert>
      ) : null}

      <div className="flex flex-col gap-6 lg:flex-row">
        <ConfigurationSidebar
          configurations={configurations}
          selectedId={selectedConfiguration?.configuration_id ?? null}
          onSelect={handleSelectConfiguration}
          onCreateFromActive={handleCreateFromActive}
          onCreateBlank={handleCreateBlank}
          onActivate={handleActivate}
          isCreating={createMutation.isPending}
          isActivating={activateMutation.isPending}
        />

        <main className="flex-1 space-y-6">
          {selectedConfiguration ? (
            <ConfigurationSummary configuration={selectedConfiguration} />
          ) : isLoading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-soft">
              Loading configuration summary…
            </div>
          ) : (
            <Alert tone="info" heading="No configurations yet">
              Create a draft configuration to begin defining columns and scripts.
            </Alert>
          )}

          <nav className="flex gap-2 rounded-full border border-slate-200 bg-white p-1 shadow-soft">
            {VIEW_OPTIONS.map((option) => {
              const isActive = option.id === viewParam;
              return (
                <Button
                  key={option.id}
                  variant={isActive ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => handleChangeView(option.id)}
                >
                  {option.label}
                </Button>
              );
            })}
          </nav>

          {viewParam === "scripts" ? (
            <ConfigurationScriptPanel
              workspaceId={workspace.id}
              configurationId={selectedConfiguration?.configuration_id ?? null}
              canonicalKey={requestedColumn ?? null}
              selectedScriptVersionId={requestedScriptVersionId}
              onSelectScriptVersion={handleSelectScriptVersion}
            />
          ) : (
            <ConfigurationColumnsEditor
              workspaceId={workspace.id}
              configurationId={selectedConfiguration?.configuration_id ?? null}
              onManageScript={handleManageScript}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function ConfigurationSummary({ configuration }: { readonly configuration: ConfigurationRecord }) {
  const status = configuration.is_active ? "Active" : "Draft";
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{configuration.title}</h2>
          <p className="text-sm text-slate-500">Version {configuration.version}</p>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${
            configuration.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700"
          }`}
        >
          {status}
        </span>
      </div>
      <dl className="mt-4 grid gap-4 md:grid-cols-2">
        <SummaryRow label="Created">{formatTimestamp(configuration.created_at)}</SummaryRow>
        <SummaryRow label="Updated">{formatTimestamp(configuration.updated_at)}</SummaryRow>
        <SummaryRow label="Activated">
          {configuration.activated_at ? formatTimestamp(configuration.activated_at) : "Not activated"}
        </SummaryRow>
        <SummaryRow label="Workspace">{configuration.workspace_id}</SummaryRow>
      </dl>
    </section>
  );
}

function SummaryRow({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-700">{children}</dd>
    </div>
  );
}

function formatTimestamp(value: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  } catch {
    return value;
  }
}

function buildDraftTitle(
  configurations: readonly ConfigurationRecord[] | undefined,
  fallback: string,
) {
  if (!configurations || configurations.length === 0) {
    return `${fallback} 1`;
  }
  const highestVersion = configurations.reduce((max, config) => Math.max(max, config.version), 0);
  return `${fallback} v${highestVersion + 1}`;
}
