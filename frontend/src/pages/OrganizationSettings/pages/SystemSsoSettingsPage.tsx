import { useEffect, useMemo, useState } from "react";

import { mapUiError } from "@/api/uiErrors";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import {
  useCreateSsoProviderMutation,
  useDeleteSsoProviderMutation,
  useSsoProvidersQuery,
  useSsoSettingsQuery,
  useUpdateSsoProviderMutation,
  useUpdateSsoSettingsMutation,
} from "@/hooks/admin";
import type { SsoProviderAdmin } from "@/api/admin/sso";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SettingsDrawer } from "@/pages/Workspace/sections/Settings/components/SettingsDrawer";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";

const STATUS_OPTIONS = ["active", "disabled"] as const;
const PROVIDER_ID_PATTERN = /^[a-z0-9][a-z0-9-_]*$/;
const DOMAIN_PATTERN = /^[a-z0-9.-]+\.[a-z]{2,}$/i;

type FeedbackTone = "success" | "danger";
type FeedbackMessage = { tone: FeedbackTone; message: string };

type ProviderStatus = "active" | "disabled";

type ProviderFieldErrors = {
  readonly id?: string;
  readonly label?: string;
  readonly issuer?: string;
  readonly clientId?: string;
  readonly clientSecret?: string;
  readonly domains?: string;
};

export function SystemSsoSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const canManage = hasPermission("system.settings.manage");
  const canRead = hasPermission("system.settings.read") || canManage;

  const providersQuery = useSsoProvidersQuery({ enabled: canRead });
  const settingsQuery = useSsoSettingsQuery({ enabled: canRead });

  const createProvider = useCreateSsoProviderMutation();
  const updateProvider = useUpdateSsoProviderMutation();
  const deleteProvider = useDeleteSsoProviderMutation();
  const updateSettings = useUpdateSsoSettingsMutation();

  const [feedback, setFeedback] = useState<FeedbackMessage | null>(null);
  const [settingsEnabled, setSettingsEnabled] = useState(false);
  const [settingsEnforceSso, setSettingsEnforceSso] = useState(false);
  const [settingsAllowJitProvisioning, setSettingsAllowJitProvisioning] = useState(true);
  const [drawerMode, setDrawerMode] = useState<"create" | "edit" | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof settingsQuery.data?.enabled === "boolean") {
      setSettingsEnabled(settingsQuery.data.enabled);
    }
    if (typeof settingsQuery.data?.enforceSso === "boolean") {
      setSettingsEnforceSso(settingsQuery.data.enforceSso);
    }
    if (typeof settingsQuery.data?.allowJitProvisioning === "boolean") {
      setSettingsAllowJitProvisioning(settingsQuery.data.allowJitProvisioning);
    }
  }, [
    settingsQuery.data?.allowJitProvisioning,
    settingsQuery.data?.enabled,
    settingsQuery.data?.enforceSso,
  ]);

  const providers = providersQuery.data?.items ?? [];
  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === selectedProviderId),
    [providers, selectedProviderId],
  );

  const hasUnsavedSsoSetting =
    typeof settingsQuery.data?.enabled === "boolean" &&
    typeof settingsQuery.data?.enforceSso === "boolean" &&
    typeof settingsQuery.data?.allowJitProvisioning === "boolean" &&
    (
      settingsEnabled !== settingsQuery.data.enabled ||
      settingsEnforceSso !== settingsQuery.data.enforceSso ||
      settingsAllowJitProvisioning !== settingsQuery.data.allowJitProvisioning
    );

  if (!canRead) {
    return <Alert tone="danger">You do not have permission to access SSO settings.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {providersQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(providersQuery.error, { fallback: "Unable to load SSO providers." }).message}
        </Alert>
      ) : null}
      {settingsQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(settingsQuery.error, { fallback: "Unable to load SSO settings." }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="Global SSO"
        description="Enable or disable SSO for this organization."
        actions={
          <Button
            type="button"
            disabled={!canManage || updateSettings.isPending || !hasUnsavedSsoSetting}
            onClick={async () => {
              setFeedback(null);
              try {
                await updateSettings.mutateAsync({
                  enabled: settingsEnabled,
                  enforceSso: settingsEnforceSso,
                  allowJitProvisioning: settingsAllowJitProvisioning,
                });
                setFeedback({ tone: "success", message: "SSO settings updated." });
              } catch (error) {
                const mapped = mapUiError(error, {
                  fallback: "Unable to update SSO settings.",
                });
                setFeedback({ tone: "danger", message: mapped.message });
              }
            }}
          >
            {updateSettings.isPending ? "Saving..." : "Save"}
          </Button>
        }
      >
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={settingsEnabled}
            onChange={(event) => setSettingsEnabled(event.target.checked)}
            disabled={!canManage || updateSettings.isPending || settingsQuery.isLoading}
          />
          Enable SSO
        </label>

        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={settingsEnforceSso}
            onChange={(event) => setSettingsEnforceSso(event.target.checked)}
            disabled={!canManage || updateSettings.isPending || settingsQuery.isLoading}
          />
          Enforce SSO for non-admin users
        </label>

        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={settingsAllowJitProvisioning}
            onChange={(event) => setSettingsAllowJitProvisioning(event.target.checked)}
            disabled={!canManage || updateSettings.isPending || settingsQuery.isLoading}
          />
          Allow just-in-time user provisioning
        </label>

        {hasUnsavedSsoSetting ? (
          <p className="text-xs font-medium text-warning">You have unsaved SSO changes.</p>
        ) : null}
      </SettingsSection>

      <SettingsSection
        title="SSO providers"
        description={`${providers.length} provider${providers.length === 1 ? "" : "s"}`}
        actions={
          canManage ? (
            <Button
              type="button"
              size="sm"
              onClick={() => {
                setSelectedProviderId(null);
                setDrawerMode("create");
              }}
            >
              Add provider
            </Button>
          ) : null
        }
      >
        {providersQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading providers...</p>
        ) : providers.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No providers configured.
          </p>
        ) : (
          <ResponsiveAdminTable
            items={providers}
            getItemKey={(provider) => provider.id}
            mobileListLabel="SSO providers"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Provider</TableHead>
                      <TableHead className="px-4">Issuer</TableHead>
                      <TableHead className="px-4">Status</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {providers.map((provider) => (
                      <TableRow key={provider.id} className="text-sm text-foreground">
                        <TableCell className="space-y-1 px-4 py-3">
                          <p className="font-semibold text-foreground">{provider.label}</p>
                          <p className="font-mono text-xs text-muted-foreground">{provider.id}</p>
                        </TableCell>
                        <TableCell className="px-4 py-3 text-muted-foreground">{provider.issuer}</TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant={provider.status === "active" ? "secondary" : "outline"}>
                            {provider.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={!canManage}
                            onClick={() => {
                              setSelectedProviderId(provider.id);
                              setDrawerMode("edit");
                            }}
                          >
                            Manage
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(provider) => (
              <>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-foreground">{provider.label}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">{provider.id}</p>
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Issuer</dt>
                  <dd className="break-all text-muted-foreground">{provider.issuer}</dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                  <dd>
                    <Badge variant={provider.status === "active" ? "secondary" : "outline"}>
                      {provider.status}
                    </Badge>
                  </dd>
                </dl>
                <div className="flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={!canManage}
                    onClick={() => {
                      setSelectedProviderId(provider.id);
                      setDrawerMode("edit");
                    }}
                  >
                    Manage
                  </Button>
                </div>
              </>
            )}
          />
        )}

        {!canManage ? (
          <Alert tone="info">You can view providers, but you need system management permission to update them.</Alert>
        ) : null}
      </SettingsSection>

      <ProviderDrawer
        open={drawerMode === "create"}
        mode="create"
        provider={undefined}
        onClose={() => setDrawerMode(null)}
        isSubmitting={createProvider.isPending || updateProvider.isPending || deleteProvider.isPending}
        onCreate={async (payload) => {
          setFeedback(null);
          await createProvider.mutateAsync(payload);
          setFeedback({ tone: "success", message: "SSO provider created." });
          setDrawerMode(null);
        }}
        onUpdate={async () => undefined}
        onDelete={undefined}
      />

      <ProviderDrawer
        open={drawerMode === "edit"}
        mode="edit"
        provider={selectedProvider}
        onClose={() => setDrawerMode(null)}
        isSubmitting={createProvider.isPending || updateProvider.isPending || deleteProvider.isPending}
        onCreate={async () => undefined}
        onUpdate={async (payload) => {
          if (!selectedProvider) return;
          setFeedback(null);
          await updateProvider.mutateAsync({ id: selectedProvider.id, payload });
          setFeedback({ tone: "success", message: "SSO provider updated." });
          setDrawerMode(null);
        }}
        onDelete={
          selectedProvider
            ? async () => {
                setFeedback(null);
                await deleteProvider.mutateAsync(selectedProvider.id);
                setFeedback({ tone: "success", message: "SSO provider disabled." });
                setDrawerMode(null);
              }
            : undefined
        }
      />
    </div>
  );
}

function ProviderDrawer({
  open,
  mode,
  provider,
  onClose,
  isSubmitting,
  onCreate,
  onUpdate,
  onDelete,
}: {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly provider?: SsoProviderAdmin;
  readonly onClose: () => void;
  readonly isSubmitting: boolean;
  readonly onCreate: (payload: {
    id: string;
    label: string;
    issuer: string;
    client_id: string;
    client_secret: string;
    status: ProviderStatus;
    domains: string[];
  }) => Promise<void>;
  readonly onUpdate: (payload: {
    label?: string;
    issuer?: string;
    client_id?: string;
    client_secret?: string;
    status?: ProviderStatus;
    domains?: string[];
  }) => Promise<void>;
  readonly onDelete?: () => Promise<void>;
}) {
  const [id, setId] = useState("");
  const [label, setLabel] = useState("");
  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [status, setStatus] = useState<ProviderStatus>("active");
  const [domains, setDomains] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<ProviderFieldErrors>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  useEffect(() => {
    if (!open) {
      setError(null);
      setFieldErrors({});
      setSubmitAttempted(false);
      return;
    }

    if (mode === "edit" && provider) {
      setId(provider.id);
      setLabel(provider.label);
      setIssuer(provider.issuer);
      setClientId(provider.client_id);
      setClientSecret("");
      setStatus(provider.status as ProviderStatus);
      setDomains((provider.domains ?? []).join(", "));
      setFieldErrors({});
      return;
    }

    setId("");
    setLabel("");
    setIssuer("");
    setClientId("");
    setClientSecret("");
    setStatus("active");
    setDomains("");
    setFieldErrors({});
  }, [mode, open, provider]);

  const parsedDomains = domains
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);

  const validationErrors = validateProviderForm({
    mode,
    id,
    label,
    issuer,
    clientId,
    clientSecret,
    domains: parsedDomains,
  });

  const shouldShowValidation = submitAttempted;

  const handleSave = async () => {
    setSubmitAttempted(true);
    setError(null);

    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setFieldErrors({});

    try {
      if (mode === "create") {
        await onCreate({
          id: id.trim(),
          label: label.trim(),
          issuer: issuer.trim(),
          client_id: clientId.trim(),
          client_secret: clientSecret.trim(),
          status,
          domains: parsedDomains,
        });
      } else {
        await onUpdate({
          label: label.trim(),
          issuer: issuer.trim(),
          client_id: clientId.trim(),
          client_secret: clientSecret.trim() || undefined,
          status,
          domains: parsedDomains,
        });
      }
    } catch (saveError) {
      const mapped = mapUiError(saveError, {
        fallback: mode === "create" ? "Unable to create provider." : "Unable to update provider.",
        statusMessages: {
          409: "A provider with this ID already exists.",
          422: "Some provider fields are invalid. Review and retry.",
        },
      });
      setFieldErrors((current) => ({
        ...current,
        id: findFirstFieldError(mapped.fieldErrors, ["id", "provider_id", "body.id"]),
        label: findFirstFieldError(mapped.fieldErrors, ["label", "body.label"]),
        issuer: findFirstFieldError(mapped.fieldErrors, ["issuer", "body.issuer"]),
        clientId: findFirstFieldError(mapped.fieldErrors, ["client_id", "clientId", "body.client_id"]),
        clientSecret: findFirstFieldError(mapped.fieldErrors, ["client_secret", "body.client_secret"]),
        domains: findFirstFieldError(mapped.fieldErrors, ["domains", "body.domains"]),
      }));
      setError(mapped.message);
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title={mode === "create" ? "Add provider" : provider?.label ?? "Provider"}
      description="Configure OIDC provider metadata and domain restrictions."
      footer={
        <div className="flex items-center justify-between gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Close
          </Button>
          <div className="flex items-center gap-2">
            {mode === "edit" && onDelete ? (
              <Button type="button" variant="destructive" size="sm" disabled={isSubmitting} onClick={onDelete}>
                Disable
              </Button>
            ) : null}
            <Button type="button" disabled={isSubmitting} onClick={handleSave}>
              {isSubmitting ? "Saving..." : mode === "create" ? "Create provider" : "Save changes"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {error ? <Alert tone="danger">{error}</Alert> : null}

        <FormField
          label="Provider ID"
          required
          hint="Lowercase letters, numbers, dashes, and underscores only."
          error={shouldShowValidation ? validationErrors.id ?? fieldErrors.id : fieldErrors.id}
        >
          <Input
            value={id}
            onChange={(event) => setId(event.target.value.toLowerCase())}
            placeholder="okta"
            disabled={mode === "edit" || isSubmitting}
          />
        </FormField>
        <FormField
          label="Label"
          required
          error={shouldShowValidation ? validationErrors.label ?? fieldErrors.label : fieldErrors.label}
        >
          <Input value={label} onChange={(event) => setLabel(event.target.value)} disabled={isSubmitting} />
        </FormField>
        <FormField
          label="Issuer"
          required
          hint="Use the provider issuer URL (for example, https://example.okta.com/oauth2/default)."
          error={shouldShowValidation ? validationErrors.issuer ?? fieldErrors.issuer : fieldErrors.issuer}
        >
          <Input value={issuer} onChange={(event) => setIssuer(event.target.value)} disabled={isSubmitting} />
        </FormField>
        <FormField
          label="Client ID"
          required
          error={shouldShowValidation ? validationErrors.clientId ?? fieldErrors.clientId : fieldErrors.clientId}
        >
          <Input value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={isSubmitting} />
        </FormField>
        <FormField
          label={mode === "create" ? "Client secret" : "Client secret (optional)"}
          required={mode === "create"}
          error={
            shouldShowValidation
              ? validationErrors.clientSecret ?? fieldErrors.clientSecret
              : fieldErrors.clientSecret
          }
        >
          <Input
            value={clientSecret}
            onChange={(event) => setClientSecret(event.target.value)}
            type="password"
            disabled={isSubmitting}
          />
        </FormField>
        <FormField label="Status">
          <select
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            value={status}
            onChange={(event) => setStatus(event.target.value as ProviderStatus)}
            disabled={isSubmitting}
          >
            {STATUS_OPTIONS.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </select>
        </FormField>
        <FormField
          label="Domains"
          hint="Comma-separated email domains allowed for this provider."
          error={shouldShowValidation ? validationErrors.domains ?? fieldErrors.domains : fieldErrors.domains}
        >
          <Input
            value={domains}
            onChange={(event) => setDomains(event.target.value)}
            placeholder="example.com, subsidiary.com"
            disabled={isSubmitting}
          />
        </FormField>
      </div>
    </SettingsDrawer>
  );
}

function validateProviderForm(input: {
  readonly mode: "create" | "edit";
  readonly id: string;
  readonly label: string;
  readonly issuer: string;
  readonly clientId: string;
  readonly clientSecret: string;
  readonly domains: readonly string[];
}): ProviderFieldErrors {
  const errors: Partial<ProviderFieldErrors> = {};

  if (input.mode === "create") {
    const providerId = input.id.trim();
    if (!providerId) {
      errors.id = "Provider ID is required.";
    } else if (!PROVIDER_ID_PATTERN.test(providerId)) {
      errors.id = "Use lowercase letters, numbers, dashes, or underscores.";
    }
  }

  if (!input.label.trim()) {
    errors.label = "Label is required.";
  }

  const issuer = input.issuer.trim();
  if (!issuer) {
    errors.issuer = "Issuer is required.";
  } else {
    try {
      const parsedUrl = new URL(issuer);
      if (!parsedUrl.protocol.startsWith("http")) {
        errors.issuer = "Issuer must be a valid http/https URL.";
      }
    } catch {
      errors.issuer = "Issuer must be a valid URL.";
    }
  }

  if (!input.clientId.trim()) {
    errors.clientId = "Client ID is required.";
  }

  if (input.mode === "create" && !input.clientSecret.trim()) {
    errors.clientSecret = "Client secret is required when creating a provider.";
  }

  const invalidDomain = input.domains.find((domain) => !DOMAIN_PATTERN.test(domain));
  if (invalidDomain) {
    errors.domains = `Invalid domain: ${invalidDomain}`;
  }

  return errors;
}

function findFirstFieldError(
  fieldErrors: Record<string, string[]>,
  keys: readonly string[],
): string | undefined {
  for (const key of keys) {
    const value = fieldErrors[key]?.[0];
    if (value) {
      return value;
    }
  }
  return undefined;
}
