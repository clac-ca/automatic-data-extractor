import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";

import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";
import { FormField } from "@ui/form-field";
import { Input, TextArea } from "@ui/input";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import {
  configsKeys,
  getConfigStatusLabel,
  getConfigStatusToneClasses,
  useActivateConfigMutation,
  useConfigFileQuery,
  useConfigFilesQuery,
  useConfigManifestQuery,
  useConfigQuery,
  useConfigSecretsQuery,
  useDeleteConfigFileMutation,
  useDeleteConfigSecretMutation,
  useLastOpenedConfig,
  useSaveConfigFileMutation,
  useSaveManifestMutation,
  useUpdateConfigMutation,
  useUpsertConfigSecretMutation,
  useValidateConfigMutation,
  type ConfigRecord,
  type ConfigSecretInput,
  type ConfigSecretMetadata,
  type ConfigValidationResponse,
  type FileItem,
  type ManifestInput,
  type ConfigStatus,
} from "@shared/configs";

export const handle = { workspaceSectionId: "configurations" } as const;

type StatusMessage = { readonly tone: "success" | "danger" | "info"; readonly message: string };

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** exponent;
  const formatted = value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${formatted} ${units[exponent]}`;
}

function inferEditorLanguage(path: string) {
  if (path.endsWith(".json")) {
    return "json";
  }
  if (path.endsWith(".py")) {
    return "python";
  }
  if (path.endsWith(".md")) {
    return "markdown";
  }
  return "plaintext";
}

export default function WorkspaceConfigEditorRoute() {
  const { workspace } = useWorkspaceContext();
  const params = useParams<{ configId: string }>();
  const configId = params.configId ?? "";
  const queryClient = useQueryClient();
  const { remember: rememberConfig } = useLastOpenedConfig(workspace.id);

  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const manifestQuery = useConfigManifestQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const filesQuery = useConfigFilesQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const secretsQuery = useConfigSecretsQuery({ workspaceId: workspace.id, configId, enabled: Boolean(configId) });
  const saveManifest = useSaveManifestMutation(workspace.id, configId);
  const validateManifest = useValidateConfigMutation(workspace.id, configId);
  const saveFile = useSaveConfigFileMutation(workspace.id, configId);
  const deleteFile = useDeleteConfigFileMutation(workspace.id, configId);
  const saveSecret = useUpsertConfigSecretMutation(workspace.id, configId);
  const removeSecret = useDeleteConfigSecretMutation(workspace.id, configId);

  const [manifestText, setManifestText] = useState<string>("{}");
  const [savedManifestText, setSavedManifestText] = useState<string>("{}");
  const [parseError, setParseError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<StatusMessage | null>(null);
  const [validationResult, setValidationResult] = useState<ConfigValidationResponse | null>(null);
  const [secretStatus, setSecretStatus] = useState<StatusMessage | null>(null);
  const [secretName, setSecretName] = useState<string>("");
  const [secretValue, setSecretValue] = useState<string>("");
  const [secretKeyId, setSecretKeyId] = useState<string>("");
  const [secretErrors, setSecretErrors] = useState<{ name?: string; value?: string }>({});
  const [removingSecretName, setRemovingSecretName] = useState<string | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string>("");
  const [fileEditorText, setFileEditorText] = useState<string>("");
  const [savedFileEditorText, setSavedFileEditorText] = useState<string>("");
  const [isCreatingNewFile, setIsCreatingNewFile] = useState<boolean>(false);
  const [fileStatus, setFileStatus] = useState<StatusMessage | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [newFilePath, setNewFilePath] = useState<string>("");
  const [newFileError, setNewFileError] = useState<string | null>(null);

  const fileQuery = useConfigFileQuery({
    workspaceId: workspace.id,
    configId,
    path: selectedFilePath,
    enabled: Boolean(configId) && Boolean(selectedFilePath) && !isCreatingNewFile,
  });

  useEffect(() => {
    if (!configId) return;
    rememberConfig(configId);
  }, [configId, rememberConfig]);

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

  useEffect(() => {
    setSecretStatus(null);
    setSecretErrors({});
    setSecretName("");
    setSecretValue("");
    setSecretKeyId("");
    setRemovingSecretName(null);
    setSelectedFilePath("");
    setFileEditorText("");
    setSavedFileEditorText("");
    setIsCreatingNewFile(false);
    setFileStatus(null);
    setFileError(null);
    setNewFileError(null);
    setNewFilePath("");
  }, [configId]);

  useEffect(() => {
    if (isCreatingNewFile) {
      return;
    }
    const items = filesQuery.data ?? [];
    if (items.length === 0) {
      if (selectedFilePath) {
        setSelectedFilePath("");
        setFileEditorText("");
        setSavedFileEditorText("");
      }
      return;
    }
    if (!selectedFilePath) {
      setSelectedFilePath(items[0].path);
      return;
    }
    const exists = items.some((file) => file.path === selectedFilePath);
    if (!exists) {
      setSelectedFilePath(items[0].path);
    }
  }, [filesQuery.data, isCreatingNewFile, selectedFilePath]);

  useEffect(() => {
    if (isCreatingNewFile) {
      return;
    }
    if (fileQuery.data !== undefined) {
      setFileEditorText(fileQuery.data);
      setSavedFileEditorText(fileQuery.data);
      setFileError(null);
    }
  }, [fileQuery.data, isCreatingNewFile]);

  useEffect(() => {
    if (!fileQuery.error) {
      return;
    }
    setFileError(
      fileQuery.error instanceof Error ? fileQuery.error.message : "Unable to load file.",
    );
  }, [fileQuery.error]);

  const config = configQuery.data;
  const isLoading = configQuery.isLoading || manifestQuery.isLoading;
  const loadError = configQuery.error ?? manifestQuery.error;
  const isDirty = manifestText !== savedManifestText;
  const secrets = secretsQuery.data ?? [];
  const files = filesQuery.data ?? [];
  const selectedFile = files.find((file) => file.path === selectedFilePath) ?? null;
  const canEditConfig = config?.status === "inactive";
  const isSavingSecret = saveSecret.isPending;
  const isRemovingSecret = removeSecret.isPending;
  const isSavingFile = saveFile.isPending;
  const isDeletingFile = deleteFile.isPending;
  const isFileDirty = isCreatingNewFile || fileEditorText !== savedFileEditorText;
  const isFileLoading = fileQuery.isLoading || fileQuery.isFetching;

  const invalidateConfigCaches = () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.root(workspace.id) });
    if (configId) {
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspace.id, configId) });
    }
  };

  const handleSelectFile = (path: string) => {
    if (!path) {
      setSelectedFilePath("");
      setIsCreatingNewFile(false);
      setFileEditorText("");
      setSavedFileEditorText("");
      setFileStatus(null);
      setFileError(null);
      setNewFileError(null);
      return;
    }
    if (!isCreatingNewFile && path === selectedFilePath) {
      return;
    }
    setSelectedFilePath(path);
    setIsCreatingNewFile(false);
    setFileStatus(null);
    setFileError(null);
    setNewFileError(null);
    setFileEditorText("");
    setSavedFileEditorText("");
  };

  const handleResetFileEditor = () => {
    setFileStatus(null);
    setFileError(null);
    if (isCreatingNewFile) {
      setFileEditorText("");
      return;
    }
    setFileEditorText(savedFileEditorText);
  };

  const handleNewFileSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canEditConfig) {
      return;
    }
    const trimmed = newFilePath.trim();
    if (!trimmed) {
      setNewFileError("File path is required.");
      return;
    }
    if (files.some((file) => file.path === trimmed)) {
      setNewFileError("A file with this path already exists.");
      return;
    }
    setNewFileError(null);
    setSelectedFilePath(trimmed);
    setIsCreatingNewFile(true);
    setFileEditorText("");
    setSavedFileEditorText("");
    setFileStatus({ tone: "info", message: "New file created locally. Save to persist it." });
    setFileError(null);
    setNewFilePath("");
  };

  const handleSaveFile = () => {
    if (!canEditConfig || !selectedFilePath) {
      return;
    }
    setFileStatus(null);
    setFileError(null);
    saveFile.mutate(
      { path: selectedFilePath, content: fileEditorText },
      {
        onSuccess: () => {
          setFileStatus({ tone: "success", message: "File saved." });
          setSavedFileEditorText(fileEditorText);
          setIsCreatingNewFile(false);
        },
        onError: (error) => {
          setFileStatus({
            tone: "danger",
            message: error instanceof Error ? error.message : "Unable to save file.",
          });
        },
      },
    );
  };

  const handleDeleteFile = (file: FileItem | null) => {
    if (!canEditConfig || !file) {
      return;
    }
    if (!window.confirm(`Delete ${file.path}? This action cannot be undone.`)) {
      return;
    }
    setFileStatus(null);
    setFileError(null);
    deleteFile.mutate(file.path, {
      onSuccess: () => {
        setFileStatus({ tone: "success", message: "File deleted." });
        setSelectedFilePath("");
        setFileEditorText("");
        setSavedFileEditorText("");
        setIsCreatingNewFile(false);
      },
      onError: (error) => {
        setFileStatus({
          tone: "danger",
          message: error instanceof Error ? error.message : "Unable to delete file.",
        });
      },
    });
  };

  const activateMutation = useActivateConfigMutation(workspace.id, {
    onSuccess: (record) => {
      setStatusMessage({ tone: "success", message: `Activated ${record.title}.` });
      invalidateConfigCaches();
    },
    onError: (error) => {
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : "Unable to activate configuration.",
      });
    },
  });

  const updateStatusMutation = useUpdateConfigMutation(workspace.id, {
    onSuccess: (record, variables) => {
      const status = variables?.payload.status;
      const message =
        status === "archived"
          ? `Archived ${record.title}.`
          : `Restored ${record.title} to inactive.`;
      setStatusMessage({ tone: "success", message });
      invalidateConfigCaches();
    },
    onError: (error, variables) => {
      const status = variables?.payload.status;
      const action = status === "archived" ? "archive" : "restore";
      setStatusMessage({
        tone: "danger",
        message: error instanceof Error ? error.message : `Unable to ${action} configuration.`,
      });
    },
  });

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

  const handleSaveSecret = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canEditConfig) {
      return;
    }
    setSecretStatus(null);
    const errors: { name?: string; value?: string } = {};
    const trimmedName = secretName.trim();
    const trimmedValue = secretValue.trim();

    if (!trimmedName) {
      errors.name = "Secret name is required.";
    }

    if (!trimmedValue) {
      errors.value = "Provide an encrypted secret value.";
    }

    if (Object.keys(errors).length > 0) {
      setSecretErrors(errors);
      return;
    }

    setSecretErrors({});
    const payload: ConfigSecretInput = {
      name: trimmedName,
      value: secretValue,
      key_id: secretKeyId.trim().length > 0 ? secretKeyId.trim() : null,
    };

    saveSecret.mutate(payload, {
      onSuccess: () => {
        setSecretStatus({ tone: "success", message: "Secret saved." });
        setSecretName(trimmedName);
        setSecretValue("");
        setSecretKeyId(payload.key_id ?? "");
      },
      onError: (error) => {
        setSecretStatus({
          tone: "danger",
          message: error instanceof Error ? error.message : "Unable to save secret.",
        });
      },
    });
  };

  const handleRemoveSecret = (secret: ConfigSecretMetadata) => {
    if (!canEditConfig) {
      return;
    }
    setSecretStatus(null);
    setRemovingSecretName(secret.name);
    removeSecret.mutate(secret.name, {
      onSuccess: () => {
        setSecretStatus({ tone: "success", message: "Secret removed." });
      },
      onError: (error) => {
        setSecretStatus({
          tone: "danger",
          message: error instanceof Error ? error.message : "Unable to remove secret.",
        });
      },
      onSettled: () => {
        setRemovingSecretName(null);
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
                onClick={() => config && activateMutation.mutate({ config })}
                disabled={activateMutation.isPending}
              >
                {activateMutation.isPending ? "Activating…" : "Activate"}
              </Button>
            ) : null}
            {config.status === "inactive" ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => config && updateStatusMutation.mutate({ config, payload: { status: "archived" } })}
                disabled={updateStatusMutation.isPending}
              >
                {updateStatusMutation.isPending ? "Archiving…" : "Archive"}
              </Button>
            ) : null}
            {config.status === "archived" ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => config && updateStatusMutation.mutate({ config, payload: { status: "inactive" } })}
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
              disabled={!isDirty || saveManifest.isPending || !canEditConfig}
            >
              {saveManifest.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </header>
        {!canEditConfig ? (
          <Alert tone="info">Only inactive configurations can be edited.</Alert>
        ) : null}
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

      <section className="space-y-4">
        <header className="space-y-1">
          <h2 className="text-lg font-semibold text-slate-900">Files</h2>
          <p className="text-sm text-slate-500">
            Review and edit hook scripts, column modules, and supporting files in this configuration bundle.
          </p>
        </header>
        {!canEditConfig ? (
          <Alert tone="info">Files can only be modified while the configuration is inactive.</Alert>
        ) : null}
        {fileStatus ? <Alert tone={fileStatus.tone}>{fileStatus.message}</Alert> : null}
        {filesQuery.isError ? (
          <Alert tone="danger">
            Unable to load files. {filesQuery.error instanceof Error ? filesQuery.error.message : "Try again later."}
          </Alert>
        ) : null}
        {fileError ? <Alert tone="danger">{fileError}</Alert> : null}
        <div className="grid gap-4 lg:grid-cols-[minmax(18rem,22rem)_1fr]">
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-200 bg-white/95 shadow-sm">
              {filesQuery.isLoading ? (
                <div className="p-4 text-sm text-slate-600">Loading files…</div>
              ) : files.length > 0 ? (
                <ul className="divide-y divide-slate-200">
                  {files.map((file) => {
                    const isActive = !isCreatingNewFile && selectedFilePath === file.path;
                    return (
                      <li key={file.path}>
                        <button
                          type="button"
                          onClick={() => handleSelectFile(file.path)}
                          className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white ${
                            isActive
                              ? "bg-slate-100 text-slate-900"
                              : "text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <span className="flex-1 truncate font-medium">{file.path}</span>
                          <span className="text-xs text-slate-500">{formatFileSize(file.byte_size)}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="p-4 text-sm text-slate-500">No files in this configuration yet.</div>
              )}
            </div>
            <form
              className="space-y-3 rounded-lg border border-dashed border-slate-300 bg-white/80 p-4 shadow-sm"
              onSubmit={handleNewFileSubmit}
            >
              <FormField
                label="Add new file"
                hint="Provide a relative path such as columns/member_id.py"
                error={newFileError ?? undefined}
              >
                <Input
                  value={newFilePath}
                  onChange={(event) => setNewFilePath(event.target.value)}
                  placeholder="columns/member_id.py"
                  disabled={!canEditConfig || isSavingFile}
                />
              </FormField>
              <div className="flex justify-end">
                <Button type="submit" variant="primary" size="sm" disabled={!canEditConfig || isSavingFile}>
                  Create
                </Button>
              </div>
            </form>
          </div>
          <div className="space-y-3 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-sm">
            {isCreatingNewFile ? (
              <header className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-slate-900">{selectedFilePath}</p>
                  <p className="text-xs text-slate-500">New file (not yet saved)</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSelectFile("")}
                  disabled={isSavingFile}
                >
                  Cancel
                </Button>
              </header>
            ) : selectedFile ? (
              <header className="space-y-1">
                <p className="text-sm font-medium text-slate-900">{selectedFile.path}</p>
                <p className="text-xs text-slate-500">
                  {formatFileSize(selectedFile.byte_size)} • SHA-256 {selectedFile.sha256.slice(0, 12)}…
                </p>
              </header>
            ) : (
              <div className="text-sm text-slate-600">
                Select a file from the list or create a new file to begin editing.
              </div>
            )}
            {isFileLoading ? (
              <div className="text-sm text-slate-600">Loading file…</div>
            ) : selectedFilePath || isCreatingNewFile ? (
              <>
                <CodeEditor
                  language={inferEditorLanguage(selectedFilePath)}
                  value={fileEditorText}
                  onChange={(value) => setFileEditorText(value ?? "")}
                  height="24rem"
                  aria-label={selectedFilePath ? `${selectedFilePath} editor` : "New configuration file editor"}
                />
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleResetFileEditor}
                    disabled={!isFileDirty || isSavingFile}
                  >
                    Reset
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteFile(selectedFile)}
                    disabled={!canEditConfig || isCreatingNewFile || isDeletingFile || !selectedFile}
                  >
                    {isDeletingFile ? "Deleting…" : "Delete"}
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={handleSaveFile}
                    disabled={!canEditConfig || !selectedFilePath || !isFileDirty || isSavingFile}
                  >
                    {isSavingFile ? "Saving…" : "Save"}
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <header className="space-y-1">
          <h2 className="text-lg font-semibold text-slate-900">Secrets</h2>
          <p className="text-sm text-slate-500">
            Secrets are encrypted at rest and never displayed after creation. Provide the plaintext value you want encrypted and
            ADE will inject it into the sandbox environment at runtime.
          </p>
        </header>
        {!canEditConfig ? (
          <Alert tone="info">Secrets can only be modified while the configuration is inactive.</Alert>
        ) : null}
        {secretStatus ? <Alert tone={secretStatus.tone}>{secretStatus.message}</Alert> : null}
        {secretsQuery.isError ? (
          <Alert tone="danger">
            Unable to load secrets. {secretsQuery.error instanceof Error ? secretsQuery.error.message : "Try again later."}
          </Alert>
        ) : null}
        <div className="rounded-lg border border-slate-200 bg-white/95 shadow-sm">
          {secretsQuery.isLoading ? (
            <div className="p-4 text-sm text-slate-600">Loading secrets…</div>
          ) : secrets.length > 0 ? (
            <ul className="divide-y divide-slate-200">
              {secrets.map((secret) => {
                const isRemovingCurrent = isRemovingSecret && removingSecretName === secret.name;
                return (
                  <li key={secret.name} className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{secret.name}</p>
                      <p className="text-xs text-slate-500">
                        Key ID {secret.key_id} • Added {new Date(secret.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveSecret(secret)}
                      disabled={!canEditConfig || isRemovingSecret}
                    >
                      {isRemovingCurrent ? "Removing…" : "Remove"}
                    </Button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="p-4 text-sm text-slate-500">No secrets added yet.</div>
          )}
        </div>
        <form
          className="grid gap-4 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-sm md:grid-cols-2"
          onSubmit={handleSaveSecret}
        >
          <FormField label="Secret name" required error={secretErrors.name}>
            <Input
              value={secretName}
              onChange={(event) => setSecretName(event.target.value)}
              placeholder="OPENAI_API_KEY"
              invalid={Boolean(secretErrors.name)}
              disabled={!canEditConfig || isSavingSecret}
            />
          </FormField>
          <FormField
            label="Key ID"
            hint="Optional. Leave blank to use the workspace default key."
          >
            <Input
              value={secretKeyId}
              onChange={(event) => setSecretKeyId(event.target.value)}
              placeholder="default"
              disabled={!canEditConfig || isSavingSecret}
            />
          </FormField>
          <FormField
            label="Secret value"
            required
            error={secretErrors.value}
            className="md:col-span-2"
          >
            <TextArea
              value={secretValue}
              onChange={(event) => setSecretValue(event.target.value)}
              rows={4}
              placeholder="Paste the plaintext secret here."
              invalid={Boolean(secretErrors.value)}
              disabled={!canEditConfig || isSavingSecret}
            />
          </FormField>
          <div className="flex items-center justify-end gap-2 md:col-span-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setSecretName("");
                setSecretValue("");
                setSecretKeyId("");
                setSecretErrors({});
                setSecretStatus(null);
              }}
              disabled={isSavingSecret}
            >
              Clear
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={!canEditConfig || isSavingSecret}>
              {isSavingSecret ? "Saving…" : "Save secret"}
            </Button>
          </div>
        </form>
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
