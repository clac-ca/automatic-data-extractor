import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { PageState } from "@ui/PageState";
import { Input } from "@ui/input";
import { Select } from "@ui/select";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import { useConfigsQuery, useCreateConfigMutation } from "@shared/configs";
import { createScopedStorage } from "@shared/storage";

const buildStorageKey = (workspaceId: string) => `ade.ui.workspace.${workspaceId}.configs.last`;

const TEMPLATE_OPTIONS = [{ value: "default", label: "Default template" }] as const;

type LastSelection = { readonly configId?: string | null } | null;

export const handle = { workspaceSectionId: "configurations" } as const;

export default function WorkspaceConfigsIndexRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const storage = useMemo(() => createScopedStorage(buildStorageKey(workspace.id)), [workspace.id]);
  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });
  const createConfig = useCreateConfigMutation(workspace.id);
  const [displayName, setDisplayName] = useState(() => `${workspace.name} Config`);
  const [templateId, setTemplateId] = useState<string>(TEMPLATE_OPTIONS[0]?.value ?? "default");
  const [validationError, setValidationError] = useState<string | null>(null);

  const configs = useMemo(
    () => (configsQuery.data?.items ?? []).filter((config) => !config.deleted_at),
    [configsQuery.data],
  );

  useEffect(() => {
    if (!configs || configs.length === 0) {
      return;
    }
    const stored = storage.get<LastSelection>();
    const preferred = stored?.configId
      ? configs.find((config) => config.config_id === stored.configId)
      : undefined;
    const target = preferred ?? configs.find((config) => config.active_version) ?? configs[0];
    if (target) {
      navigate(`${target.config_id}`, { replace: true });
    }
  }, [configs, navigate, storage]);

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
          storage.set<LastSelection>({ configId: record.config_id });
        },
      },
    );
  };

  const creationError = validationError ?? (createConfig.error instanceof Error ? createConfig.error.message : null);
  const canSubmit = displayName.trim().length > 0 && !createConfig.isPending;

  if (configsQuery.isLoading) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Loading configuration editor…</p>
      </div>
    );
  }

  if (configsQuery.isError) {
    return (
      <div className="space-y-2 text-sm text-slate-600">
        <p>Unable to load configurations.</p>
      </div>
    );
  }

  if (configs.length === 0) {
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
            {creationError ? (
              <p className="text-sm font-medium text-danger-600">{creationError}</p>
            ) : null}
            <Button type="submit" className="w-full" disabled={!canSubmit} isLoading={createConfig.isPending}>
              Create from template
            </Button>
          </form>
        }
      />
    );
  }

  return (
    <div className="space-y-2 text-sm text-slate-600">
      <p>No configurations available yet. Create one from the Configs editor.</p>
    </div>
  );
}
