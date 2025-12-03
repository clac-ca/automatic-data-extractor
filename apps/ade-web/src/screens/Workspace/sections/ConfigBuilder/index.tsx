import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { Select } from "@ui/Select";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import {
  useConfigurationsQuery,
  useCreateConfigurationMutation,
  useImportConfigurationMutation,
} from "@shared/configurations";
import { buildLastSelectionStorageKey, createLastSelectionStorage, persistLastSelection, type LastSelection } from "./storage";

const TEMPLATE_OPTIONS = [{ value: "default", label: "Default template" }] as const;

const buildConfigDetailPath = (workspaceId: string, configId: string) =>
  `/workspaces/${workspaceId}/config-builder/${encodeURIComponent(configId)}`;

export const handle = { workspaceSectionId: "config-builder" } as const;

export default function WorkspaceConfigsIndexRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const storageKey = useMemo(() => buildLastSelectionStorageKey(workspace.id), [workspace.id]);
  const storage = useMemo(() => createLastSelectionStorage(workspace.id), [workspace.id]);
  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });
  const createConfig = useCreateConfigurationMutation(workspace.id);
  const importConfig = useImportConfigurationMutation(workspace.id);

  const [displayName, setDisplayName] = useState(() => `${workspace.name} Config`);
  const [templateId, setTemplateId] = useState<string>(TEMPLATE_OPTIONS[0]?.value ?? "default");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [importDisplayName, setImportDisplayName] = useState(() => `${workspace.name} Import`);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [lastSelection, setLastSelection] = useState<LastSelection>(() => storage.get<LastSelection>());
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const lastWorkspaceRef = useRef<{ id: string; name: string } | null>(null);

  const configurations = useMemo(
    () =>
      (configurationsQuery.data?.items ?? []).filter(
        (config) => !("deleted_at" in config && (config as { deleted_at?: string | null }).deleted_at),
      ),
    [configurationsQuery.data],
  );
  const lastOpenedConfig = useMemo(
    () => configurations.find((config) => config.id === lastSelection?.configId) ?? null,
    [configurations, lastSelection],
  );

  const updateLastSelection = useCallback(
    (configId: string | null) => {
      setLastSelection(persistLastSelection(storage, configId));
    },
    [storage],
  );

  useEffect(() => {
    setLastSelection(storage.get<LastSelection>());
  }, [storage]);

  useEffect(() => {
    const previous = lastWorkspaceRef.current;
    const idChanged = previous?.id !== workspace.id;
    const nameChanged = previous?.name !== workspace.name;
    if (!idChanged && !nameChanged) {
      return;
    }
    lastWorkspaceRef.current = { id: workspace.id, name: workspace.name };

    if (idChanged) {
      setDisplayName(`${workspace.name} Config`);
      setTemplateId(TEMPLATE_OPTIONS[0]?.value ?? "default");
      setValidationError(null);
      setImportDisplayName(`${workspace.name} Import`);
      setImportFile(null);
      setImportError(null);
      if (importInputRef.current) {
        importInputRef.current.value = "";
      }
      return;
    }

    if (nameChanged) {
      setDisplayName((current) => (current === `${previous?.name ?? ""} Config` ? `${workspace.name} Config` : current));
      setImportDisplayName((current) => (current === `${previous?.name ?? ""} Import` ? `${workspace.name} Import` : current));
    }
  }, [workspace.id, workspace.name]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.storageArea !== window.localStorage || event.key !== storageKey) {
        return;
      }
      try {
        setLastSelection(event.newValue ? (JSON.parse(event.newValue) as LastSelection) : null);
      } catch {
        setLastSelection(null);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [storageKey]);

  useEffect(() => {
    if (!lastSelection?.configId) {
      return;
    }
    if (configurations.some((config) => config.id === lastSelection.configId)) {
      return;
    }
    updateLastSelection(null);
  }, [configurations, lastSelection?.configId, updateLastSelection]);

  const handleOpenConfig = (configId: string) => {
    updateLastSelection(configId);
    navigate(buildConfigDetailPath(workspace.id, configId));
  };

  const handleOpenEditor = (configId: string) => {
    updateLastSelection(configId);
    navigate(`${buildConfigDetailPath(workspace.id, configId)}/editor`);
  };

  const handleImportFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setImportError(null);
    setImportFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  }, []);

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
          updateLastSelection(record.id);
          navigate(buildConfigDetailPath(workspace.id, record.id));
        },
      },
    );
  };

  const handleImport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = importDisplayName.trim();
    if (!trimmedName) {
      setImportError("Enter a display name for the imported configuration.");
      return;
    }
    if (!importFile) {
      setImportError("Select a .zip file to import.");
      return;
    }
    setImportError(null);
    importConfig.mutate(
      { displayName: trimmedName, file: importFile },
      {
        onSuccess(record) {
          updateLastSelection(record.id);
          setImportFile(null);
          void configurationsQuery.refetch();
          navigate(buildConfigDetailPath(workspace.id, record.id));
        },
        onError(error) {
          setImportError(error instanceof Error ? error.message : "Unable to import configuration.");
        },
      },
    );
  };

  const creationError = validationError ?? (createConfig.error instanceof Error ? createConfig.error.message : null);
  const canSubmit = displayName.trim().length > 0 && !createConfig.isPending;
  const canImport = importDisplayName.trim().length > 0 && Boolean(importFile) && !importConfig.isPending;

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
          <div className="space-y-6 text-left">
            <form onSubmit={handleCreate} className="space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
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
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-slate-900">Import configuration</h2>
                <p className="text-sm text-slate-500">Upload an ADE export (.zip) to create a new draft configuration.</p>
              </div>
              <form onSubmit={handleImport} className="mt-3 space-y-4">
                <FormField label="Configuration name" required>
                  <Input
                    value={importDisplayName}
                    onChange={(event) => setImportDisplayName(event.target.value)}
                    placeholder="Imported configuration"
                    disabled={importConfig.isPending}
                  />
                </FormField>
                <FormField label="Archive (.zip)" required>
                  <Input
                    type="file"
                    ref={importInputRef}
                    accept=".zip"
                    onChange={handleImportFileChange}
                    disabled={importConfig.isPending}
                  />
                  {importFile ? (
                    <p className="mt-1 text-xs text-slate-500" aria-live="polite">
                      {importFile.name}
                    </p>
                  ) : null}
                </FormField>
                {importError ? <p className="text-sm font-medium text-danger-600">{importError}</p> : null}
                <Button type="submit" className="w-full" disabled={!canImport} isLoading={importConfig.isPending}>
                  Import archive
                </Button>
              </form>
            </div>
          </div>
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
          {lastOpenedConfig ? (
            <Button variant="ghost" size="sm" onClick={() => handleOpenConfig(lastOpenedConfig.id)}>
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
                  {lastOpenedConfig?.id === config.id ? (
                    <span className="text-xs font-medium uppercase tracking-wide text-brand-600">Last opened</span>
                  ) : null}
                </div>
                <p className="text-sm text-slate-500">Updated {formatTimestamp(config.updated_at)}</p>
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
        <div className="border-t border-slate-200 pt-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-slate-900">Import configuration</h2>
            <p className="text-sm text-slate-500">Upload an ADE export (.zip) to create a new draft configuration.</p>
          </div>
          <form onSubmit={handleImport} className="mt-3 space-y-4">
            <FormField label="Configuration name" required>
              <Input
                value={importDisplayName}
                onChange={(event) => setImportDisplayName(event.target.value)}
                placeholder="Imported configuration"
                disabled={importConfig.isPending}
              />
            </FormField>
            <FormField label="Archive (.zip)" required>
              <Input
                type="file"
                ref={importInputRef}
                accept=".zip"
                onChange={handleImportFileChange}
                disabled={importConfig.isPending}
              />
              {importFile ? (
                <p className="mt-1 text-xs text-slate-500" aria-live="polite">
                  {importFile.name}
                </p>
              ) : null}
            </FormField>
            {importError ? <p className="text-sm font-medium text-danger-600">{importError}</p> : null}
            <Button type="submit" className="w-full" disabled={!canImport} isLoading={importConfig.isPending}>
              Import archive
            </Button>
          </form>
        </div>
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
