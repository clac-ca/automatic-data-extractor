import { useCallback, useMemo, useState } from "react";

import { useNavigate } from "@app/nav/history";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import {
  useActivateConfigurationMutation,
  useConfigFileQuery,
  useConfigQuery,
  useDeactivateConfigurationMutation,
  useValidateConfigurationMutation,
  type ConfigurationValidateResponse,
  type FileReadJson,
} from "@shared/configs";
import { createScopedStorage } from "@shared/storage";

interface ManifestColumnSummary {
  readonly key: string;
  readonly label: string;
  readonly path: string;
  readonly required: boolean;
  readonly enabled: boolean;
}

interface ManifestSummary {
  readonly name: string;
  readonly columns: readonly ManifestColumnSummary[];
  readonly transformPath: string | null;
  readonly validatorsPath: string | null;
}

interface ManifestParseResult {
  readonly summary: ManifestSummary | null;
  readonly error: string | null;
}

const MANIFEST_PATH = "src/ade_config/manifest.json";

interface WorkspaceConfigRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function WorkspaceConfigRoute({ params }: WorkspaceConfigRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const configId = params?.configId;
  const navigate = useNavigate();

  const storage = useMemo(
    () => createScopedStorage(`ade.ui.workspace.${workspace.id}.config.${configId ?? "unknown"}.editor`),
    [workspace.id, configId],
  );

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId: configId ?? "", enabled: Boolean(configId) });
  const manifestQuery = useConfigFileQuery({ workspaceId: workspace.id, configId: configId ?? "", path: MANIFEST_PATH, enabled: Boolean(configId) });
  const validateMutation = useValidateConfigurationMutation(workspace.id, configId ?? "");
  const activateMutation = useActivateConfigurationMutation(workspace.id, configId ?? "");
  const deactivateMutation = useDeactivateConfigurationMutation(workspace.id, configId ?? "");

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const manifestDetails = useMemo(() => parseManifestFile(manifestQuery.data), [manifestQuery.data]);
  const manifestError = manifestDetails.error ?? (manifestQuery.isError ? (manifestQuery.error as Error).message : null);

  const configData = configQuery.data;
  const editable = configData?.status === "draft";

  const handleValidate = useCallback(async () => {
    if (!configId) {
      return;
    }
    setStatusMessage(null);
    setStatusError(null);
    try {
      await validateMutation.mutateAsync();
      setStatusMessage("Validation completed.");
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "Validation failed.");
    }
  }, [configId, validateMutation]);

  const handleActivate = useCallback(async () => {
    if (!configId) {
      return;
    }
    setStatusMessage(null);
    setStatusError(null);
    try {
      await activateMutation.mutateAsync();
      await configQuery.refetch();
      setStatusMessage("Configuration activated.");
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "Activate failed.");
    }
  }, [activateMutation, configId, configQuery]);

  const handleDeactivate = useCallback(async () => {
    if (!configId) {
      return;
    }
    setStatusMessage(null);
    setStatusError(null);
    try {
      await deactivateMutation.mutateAsync();
      await configQuery.refetch();
      setStatusMessage("Configuration deactivated.");
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "Deactivate failed.");
    }
  }, [configId, deactivateMutation, configQuery]);

  const handleOpenEditor = useCallback(
    (path?: string | null) => {
      if (!configId) {
        return;
      }
      const stored = storage.get<Record<string, unknown>>();
      const storedPath = typeof stored?.lastPath === "string" ? stored.lastPath : null;
      const target = path ?? storedPath;
      const basePath = `/workspaces/${workspace.id}/configs/${encodeURIComponent(configId)}/editor`;
      const search = target ? `?path=${encodeURIComponent(target)}` : "";
      navigate(`${basePath}${search}`);
    },
    [configId, navigate, storage, workspace.id],
  );

  if (!configId) {
    return <PageState title="Select a configuration" description="Choose a configuration to open." />;
  }

  if (configQuery.isLoading) {
    return <PageState variant="loading" title="Loading configuration" description="Fetching configuration details…" />;
  }

  if (configQuery.isError || !configData) {
    return <PageState variant="error" title="Configuration not found" description="This configuration could not be loaded." />;
  }

  return (
    <div className="space-y-6 p-4">
      <ConfigHeader
        configName={configData.display_name}
        workspaceName={workspace.name}
        status={configData.status}
        updatedAt={configData.updated_at}
        onValidate={handleValidate}
        onActivate={handleActivate}
        onDeactivate={handleDeactivate}
        validating={validateMutation.isPending}
        lifecyclePending={activateMutation.isPending || deactivateMutation.isPending}
        canActivate={configData.status !== "active"}
        canDeactivate={configData.status === "active"}
        onOpenEditor={() => handleOpenEditor()}
      />

      {statusMessage ? <Alert tone="success">{statusMessage}</Alert> : null}
      {statusError ? <Alert tone="danger">{statusError}</Alert> : null}

      {!editable ? (
        <Alert tone="warning" heading="Read-only configuration">
          This configuration is {configData.status}. Switch to a draft to make changes.
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr),minmax(0,1fr)]">
        <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <header className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Configuration files</h2>
              <p className="text-sm text-slate-500">Open the dedicated editor to modify scripts and hooks.</p>
            </div>
            <Button onClick={() => handleOpenEditor()}>Open code editor</Button>
          </header>
          <p className="text-sm text-slate-600">
            Manage detector scripts, hooks, and configuration files from the new workbench. Your last opened file is restored automatically.
          </p>
        </section>

        <aside className="space-y-4">
          <ManifestPanel
            manifest={{ summary: manifestDetails.summary, error: manifestError, isLoading: manifestQuery.isLoading }}
            manifestPath={MANIFEST_PATH}
            onOpenManifest={() => handleOpenEditor(MANIFEST_PATH)}
            onOpenFile={(path) => {
              if (path) {
                handleOpenEditor(path);
              }
            }}
          />
          <ValidationPanel
            validation={validateMutation.data ?? null}
            validationError={validateMutation.isError ? (validateMutation.error as Error).message : null}
            isValidationRunning={validateMutation.isPending}
            onValidate={handleValidate}
          />
        </aside>
      </div>
    </div>
  );
}

function ConfigHeader({
  configName,
  workspaceName,
  status,
  updatedAt,
  onValidate,
  onActivate,
  onDeactivate,
  validating,
  lifecyclePending,
  canActivate,
  canDeactivate,
  onOpenEditor,
}: {
  readonly configName: string;
  readonly workspaceName: string;
  readonly status: string;
  readonly updatedAt: string;
  readonly onValidate: () => void;
  readonly onActivate: () => void;
  readonly onDeactivate: () => void;
  readonly validating: boolean;
  readonly lifecyclePending: boolean;
  readonly canActivate: boolean;
  readonly canDeactivate: boolean;
  readonly onOpenEditor: () => void;
}) {
  return (
    <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-slate-500">Workspace · {workspaceName}</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">{configName}</h1>
            <StatusBadge status={status} />
          </div>
          <p className="text-sm text-slate-500">Updated {formatTimestamp(updatedAt)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onValidate} isLoading={validating}>
            Validate
          </Button>
          {canActivate ? (
            <Button variant="primary" size="sm" onClick={onActivate} isLoading={lifecyclePending}>
              Activate
            </Button>
          ) : null}
          {canDeactivate ? (
            <Button variant="ghost" size="sm" onClick={onDeactivate} isLoading={lifecyclePending}>
              Deactivate
            </Button>
          ) : null}
          <Button variant="ghost" size="sm" onClick={onOpenEditor}>
            Open code editor
          </Button>
        </div>
      </div>
    </header>
  );
}

function StatusBadge({ status }: { readonly status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "active"
      ? "bg-emerald-100 text-emerald-700"
      : normalized === "draft"
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-200 text-slate-700";
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${tone}`}>{status}</span>;
}

function ManifestPanel({
  manifest,
  manifestPath,
  onOpenManifest,
  onOpenFile,
}: {
  readonly manifest: { summary: ManifestSummary | null; error: string | null; isLoading: boolean };
  readonly manifestPath: string;
  readonly onOpenManifest: () => void;
  readonly onOpenFile: (path: string | null | undefined) => void;
}) {
  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Manifest</p>
          <p className="text-sm font-semibold text-slate-900">{manifest.summary?.name ?? "Configuration manifest"}</p>
        </div>
        <Button size="sm" variant="secondary" onClick={onOpenManifest}>
          Open file
        </Button>
      </header>
      {manifest.isLoading ? (
        <p className="text-sm text-slate-500">Loading manifest…</p>
      ) : manifest.error ? (
        <Alert tone="danger">{manifest.error}</Alert>
      ) : manifest.summary ? (
        <div className="space-y-3 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Columns</p>
            {manifest.summary.columns.length === 0 ? (
              <p className="text-sm text-slate-500">No columns defined.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {manifest.summary.columns.map((column) => (
                  <li key={column.key} className="rounded-xl border border-slate-100 px-3 py-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-slate-900">{column.label}</p>
                        <p className="truncate text-slate-500">{column.path || "No script assigned"}</p>
                      </div>
                      <span className="text-[10px] uppercase text-slate-500">
                        {column.required ? "Required" : "Optional"}
                        {!column.enabled ? " · Disabled" : ""}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-xs">
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => onOpenFile(resolveColumnPath(column.path))}
                        disabled={!column.path}
                      >
                        Manage script
                      </Button>
                      {!column.enabled ? <span className="text-[10px] uppercase text-amber-600">Disabled</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="space-y-1 text-xs text-slate-600">
            <p>
              Transform: {" "}
              {manifest.summary.transformPath ? (
                <button
                  type="button"
                  className="text-brand-700 hover:underline"
                  onClick={() => onOpenFile(resolveColumnPath(manifest.summary.transformPath))}
                >
                  {manifest.summary.transformPath}
                </button>
              ) : (
                "—"
              )}
            </p>
            <p>
              Validators: {" "}
              {manifest.summary.validatorsPath ? (
                <button
                  type="button"
                  className="text-brand-700 hover:underline"
                  onClick={() => onOpenFile(resolveColumnPath(manifest.summary.validatorsPath))}
                >
                  {manifest.summary.validatorsPath}
                </button>
              ) : (
                "—"
              )}
            </p>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500">Manifest file not found ({manifestPath}).</p>
      )}
    </section>
  );
}

function ValidationPanel({
  validation,
  validationError,
  isValidationRunning,
  onValidate,
}: {
  readonly validation: ConfigurationValidateResponse | null;
  readonly validationError: string | null;
  readonly isValidationRunning: boolean;
  readonly onValidate: () => void;
}) {
  const hasIssues = Boolean(validation?.issues?.length);
  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Validation</p>
          <p className="text-sm font-semibold text-slate-900">
            {validation ? `Digest ${validation.content_digest ?? "—"}` : "No run yet"}
          </p>
        </div>
        <Button size="sm" onClick={onValidate} isLoading={isValidationRunning}>
          Run
        </Button>
      </header>
      {validationError ? <Alert tone="danger">{validationError}</Alert> : null}
      {validation ? (
        <div className="space-y-2 text-sm">
          <p className="text-slate-600">Status: {validation.status}</p>
          {hasIssues ? (
            <div className="space-y-2">
              {validation.issues.map((issue) => (
                <article key={`${issue.path}:${issue.message}`} className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold text-amber-800">{issue.path}</p>
                  <p className="text-sm text-amber-900">{issue.message}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="text-sm text-emerald-700">No issues reported.</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-500">Run validation to populate this panel.</p>
      )}
    </section>
  );
}

function parseManifestFile(file: FileReadJson | null): ManifestParseResult {
  if (!file) {
    return { summary: null, error: null };
  }
  if (file.encoding !== "utf-8") {
    return { summary: null, error: "Manifest file is not UTF-8 encoded." };
  }
  try {
    const raw = JSON.parse(file.content ?? "{}");
    const columns: ManifestColumnSummary[] = Array.isArray(raw.columns)
      ? raw.columns.map((column: Record<string, unknown>) => ({
          key: String(column.key ?? column.label ?? column.path ?? "column"),
          label: String(column.label ?? column.key ?? column.path ?? "Column"),
          path: String(column.path ?? ""),
          required: Boolean(column.required),
          enabled: column.enabled === undefined ? true : Boolean(column.enabled),
        }))
      : [];
    const summary: ManifestSummary = {
      name: typeof raw.name === "string" && raw.name.trim().length > 0 ? raw.name : "Configuration manifest",
      columns,
      transformPath: raw.table?.transform?.path ?? null,
      validatorsPath: raw.table?.validators?.path ?? null,
    };
    return { summary, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to parse manifest.";
    return { summary: null, error: message };
  }
}

function resolveColumnPath(path: string | null | undefined) {
  if (!path) {
    return null;
  }
  if (path.startsWith("src/")) {
    return path;
  }
  return `src/ade_config/${path.replace(/^\/+/, "")}`;
}

function formatTimestamp(value?: string | Date | null) {
  if (!value) {
    return "";
  }
  try {
    const date = typeof value === "string" ? new Date(value) : value;
    return date.toLocaleString();
  } catch {
    return String(value);
  }
}
