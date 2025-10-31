import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  activateConfig,
  configsKeys,
  updateConfig,
  useConfigManifestQuery,
  useConfigQuery,
  useSaveManifestMutation,
  useValidateConfigMutation,
  type ConfigRecord,
  type ConfigValidationResponse,
  type ManifestInput,
} from "@shared/configs";
import { createScopedStorage } from "@shared/storage";

const buildStorageKey = (workspaceId: string) => `ade.ui.workspace.${workspaceId}.configs.last`;

export const handle = { workspaceSectionId: "configurations" } as const;

type StatusMessage = { readonly tone: "success" | "danger" | "info"; readonly message: string };

type ConfigStatus = ConfigRecord["status"];

function getStatusLabel(status: ConfigStatus) {
  switch (status) {
    case "active":
      return "Active";
    case "inactive":
      return "Inactive";
    case "archived":
      return "Archived";
    default:
      return status;
  }
}

function getStatusToneClasses(status: ConfigStatus) {
  switch (status) {
    case "active":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "archived":
      return "border-slate-200 bg-slate-50 text-slate-600";
    default:
      return "border-sky-200 bg-sky-50 text-sky-700";
  }
}

export default function WorkspaceConfigEditorRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";
  const queryClient = useQueryClient();
  const storage = useMemo(() => createScopedStorage(buildStorageKey(workspace.id)), [workspace.id]);

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const manifestQuery = useConfigManifestQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const saveManifest = useSaveManifestMutation(workspace.id, configId);
  const validateManifest = useValidateConfigMutation(workspace.id, configId);

  const [manifestText, setManifestText] = useState<string>("{}");
  const [savedManifestText, setSavedManifestText] = useState<string>("{}");
  const [parseError, setParseError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<StatusMessage | null>(null);
  const [validationResult, setValidationResult] = useState<ConfigValidationResponse | null>(null);

  useEffect(() => {
    if (!configId) return;
    storage.set({ configId });
  }, [configId, storage]);

  useEffect(() => {
    if (!manifestQuery.data) {
      setManifestText("{}");
      setSavedManifestText("{}");
      return;
    }
    const next = JSON.stringify(manifestQuery.data, null, 2);
    setManifestText(next);
    setSavedManifestText(next);
    setParseError(null);
  }, [manifestQuery.data]);

  const config = configQuery.data;
  const isLoading = configQuery.isLoading || manifestQuery.isLoading;
  const loadError = configQuery.error ?? manifestQuery.error;
  const isDirty = manifestText !== savedManifestText;

  const invalidateConfigCaches = () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.root(workspace.id) });
    if (configId) {
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspace.id, configId) });
    }
  };

  const activateMutation = useMutation({
    mutationFn: () => activateConfig(workspace.id, configId),
    onSuccess: () => {
      setStatusMessage({ tone: "success", message: "Configuration activated." });
      invalidateConfigCaches();
    },
    onError: (error: unknown) => {
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : "Unable to activate configuration.",
      });
    },
  });

  const updateStatusMutation = useMutation(
    (status: "inactive" | "archived") => updateConfig(workspace.id, configId, { status }),
    {
      onSuccess: (_, status) => {
        setStatusMessage({
          tone: "success",
          message: status === "archived" ? "Configuration archived." : "Configuration restored.",
        });
        invalidateConfigCaches();
      },
      onError: (error, status) => {
        const action = status === "archived" ? "archive" : "restore";
        setStatusMessage({
          tone: "danger",
          message: error instanceof Error ? error.message : `Unable to ${action} configuration.`,
        });
      },
    },
  );

  const handleSaveManifest = () => {
    setParseError(null);
    setStatusMessage(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(manifestText);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Manifest must be valid JSON.");
      return;
    }
    saveManifest.mutate(parsed as ManifestInput, {
      onSuccess: (result) => {
        const next = JSON.stringify(result, null, 2);
        setSavedManifestText(next);
        setManifestText(next);
        setStatusMessage({ tone: "success", message: "Manifest saved." });
      },
      onError: (error) => {
        setStatusMessage({
          tone: "danger",
          message: error instanceof Error ? error.message : "Unable to save manifest.",
        });
      },
    });
  };

  const handleValidate = () => {
    setStatusMessage(null);
    setValidationResult(null);
    validateManifest.mutate(undefined, {
      onSuccess: (result) => {
        setValidationResult(result);
        setStatusMessage({ tone: "success", message: "Validation completed." });
      },
      onError: (error) => {
        setStatusMessage({
          tone: "danger",
          message: error instanceof Error ? error.message : "Validation failed.",
        });
      },
    });
  };

  if (!configId) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Select a configuration to begin editing.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Loading configuration…</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <Alert tone="danger">
        Unable to load configuration. {loadError instanceof Error ? loadError.message : "Try again later."}
      </Alert>
    );
  }

  if (!config) {
    return (
      <Alert tone="danger">
        Configuration not found. It may have been deleted or you no longer have access.
      </Alert>
    );
  }

  const statusLabel = getStatusLabel(config.status as ConfigStatus);

  return (
    <div className="space-y-6">
      {statusMessage ? <Alert tone={statusMessage.tone}>{statusMessage.message}</Alert> : null}

      <section className="rounded-lg border border-slate-200 bg-white/95 p-5 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{config.title}</h1>
            <p className="text-sm text-slate-500">
              Version {config.version} • Updated {new Date(config.updated_at).toLocaleString()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${getStatusToneClasses(
                config.status as ConfigStatus,
              )}`}
            >
              {statusLabel}
            </span>
            {config.status !== "active" ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => activateMutation.mutate()}
                disabled={activateMutation.isPending}
              >
                {activateMutation.isPending ? "Activating…" : "Activate"}
              </Button>
            ) : null}
            {config.status === "inactive" ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => updateStatusMutation.mutate("archived")}
                disabled={updateStatusMutation.isPending}
              >
                {updateStatusMutation.isPending ? "Archiving…" : "Archive"}
              </Button>
            ) : null}
            {config.status === "archived" ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => updateStatusMutation.mutate("inactive")}
                disabled={updateStatusMutation.isPending}
              >
                {updateStatusMutation.isPending ? "Restoring…" : "Unarchive"}
              </Button>
            ) : null}
          </div>
        </header>
        {config.note ? <p className="mt-3 text-sm text-slate-600">{config.note}</p> : null}
      </section>

      <section className="space-y-3">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">manifest.json</h2>
            <p className="text-sm text-slate-500">
              Edit the configuration manifest. Changes are applied immediately after saving.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setManifestText(savedManifestText)}
              disabled={!isDirty || saveManifest.isPending}
            >
              Reset
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleValidate}
              disabled={validateManifest.isPending}
            >
              {validateManifest.isPending ? "Validating…" : "Validate"}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveManifest}
              disabled={!isDirty || saveManifest.isPending}
            >
              {saveManifest.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </header>
        {parseError ? <Alert tone="danger">{parseError}</Alert> : null}
        <CodeEditor
          language="json"
          value={manifestText}
          onChange={(value) => {
            setManifestText(value ?? "");
          }}
          height="28rem"
          aria-label="Configuration manifest editor"
        />
      </section>

      {validationResult ? (
        <section className="space-y-3">
          <header>
            <h2 className="text-lg font-semibold text-slate-900">Validation results</h2>
            <p className="text-sm text-slate-500">
              Last ran at {new Date().toLocaleTimeString()} ({validationResult.issues?.length ?? 0} issues)
            </p>
          </header>
          {validationResult.issues && validationResult.issues.length > 0 ? (
            <ul className="space-y-2">
              {validationResult.issues.map((issue) => (
                <li
                  key={`${issue.path}:${issue.code}`}
                  className="rounded-lg border border-slate-200 bg-white/95 p-3 text-sm text-slate-700 shadow-sm"
                >
                  <p className="font-medium text-slate-900">
                    {issue.level.toUpperCase()} · {issue.code} · {issue.path}
                  </p>
                  <p className="mt-1 text-slate-600">{issue.message}</p>
                </li>
              ))}
            </ul>
          ) : (
            <Alert tone="success">No issues detected.</Alert>
          )}
        </section>
      ) : null}
    </div>
  );
}
