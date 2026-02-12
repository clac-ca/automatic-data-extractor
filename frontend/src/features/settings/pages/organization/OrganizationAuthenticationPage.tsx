import { useEffect, useMemo, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";
import { SsoSetupFlow } from "@/features/sso-setup";

import {
  normalizeSettingsError,
  useCreateOrganizationScimTokenMutation,
  useCreateOrganizationSsoProviderMutation,
  useDeleteOrganizationSsoProviderMutation,
  useOrganizationRuntimeSettingsQuery,
  useOrganizationScimTokensQuery,
  useOrganizationSsoProvidersQuery,
  usePatchOrganizationRuntimeSettingsMutation,
  useRevokeOrganizationScimTokenMutation,
  useUpdateOrganizationSsoProviderMutation,
  useValidateOrganizationSsoProviderMutation,
} from "../../data";
import { settingsPaths } from "../../routing/contracts";
import {
  SettingsAccessDenied,
  SettingsDetailLayout,
  SettingsDetailSection,
  SettingsErrorState,
  SettingsStickyActionBar,
} from "../../shared";

function toNumberOrNull(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

const AUTHENTICATION_SECTIONS = [
  { id: "sign-in-mode", label: "Sign-in mode" },
  { id: "password-policy", label: "Password policy" },
  { id: "provisioning", label: "Provisioning" },
  { id: "sso-providers", label: "SSO providers" },
] as const;

export function OrganizationAuthenticationPage() {
  const { permissions } = useGlobalPermissions();
  const canManage = permissions.has("system.settings.manage");
  const canRead = permissions.has("system.settings.read") || canManage;

  const settingsQuery = useOrganizationRuntimeSettingsQuery(canRead);
  const providersQuery = useOrganizationSsoProvidersQuery(canRead);
  const patchMutation = usePatchOrganizationRuntimeSettingsMutation();

  const createProviderMutation = useCreateOrganizationSsoProviderMutation();
  const updateProviderMutation = useUpdateOrganizationSsoProviderMutation();
  const deleteProviderMutation = useDeleteOrganizationSsoProviderMutation();
  const validateProviderMutation = useValidateOrganizationSsoProviderMutation();

  const scimTokensQuery = useOrganizationScimTokensQuery(canRead);
  const createScimTokenMutation = useCreateOrganizationScimTokenMutation();
  const revokeScimTokenMutation = useRevokeOrganizationScimTokenMutation();

  const [mode, setMode] = useState<"password_only" | "idp_only" | "password_and_idp">("password_only");
  const [resetEnabled, setResetEnabled] = useState(true);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [minLength, setMinLength] = useState("12");
  const [requireUppercase, setRequireUppercase] = useState(false);
  const [requireLowercase, setRequireLowercase] = useState(false);
  const [requireNumber, setRequireNumber] = useState(false);
  const [requireSymbol, setRequireSymbol] = useState(false);
  const [lockoutAttempts, setLockoutAttempts] = useState("5");
  const [lockoutSeconds, setLockoutSeconds] = useState("300");
  const [provisioningMode, setProvisioningMode] = useState<"disabled" | "jit" | "scim">("jit");

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [setupFlowOpen, setSetupFlowOpen] = useState(false);
  const [setupFlowMode, setSetupFlowMode] = useState<"create" | "edit">("create");
  const [setupProviderId, setSetupProviderId] = useState<string | null>(null);
  const [setupReturnFocusTarget, setSetupReturnFocusTarget] = useState<HTMLElement | null>(null);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);

  const [scimTokenName, setScimTokenName] = useState("");
  const [scimTokenSecret, setScimTokenSecret] = useState<string | null>(null);

  const selectedSetupProvider = useMemo(
    () => providersQuery.data?.items.find((provider) => provider.id === setupProviderId),
    [providersQuery.data?.items, setupProviderId],
  );

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    const auth = settingsQuery.data.values.auth;
    setMode(auth.mode);
    setResetEnabled(auth.password.resetEnabled);
    setMfaRequired(auth.password.mfaRequired);
    setMinLength(String(auth.password.complexity.minLength));
    setRequireUppercase(auth.password.complexity.requireUppercase);
    setRequireLowercase(auth.password.complexity.requireLowercase);
    setRequireNumber(auth.password.complexity.requireNumber);
    setRequireSymbol(auth.password.complexity.requireSymbol);
    setLockoutAttempts(String(auth.password.lockout.maxAttempts));
    setLockoutSeconds(String(auth.password.lockout.durationSeconds));
    setProvisioningMode(auth.identityProvider.provisioningMode);
  }, [settingsQuery.data]);

  const hasUnsavedChanges = useMemo(() => {
    if (!settingsQuery.data) {
      return false;
    }
    const auth = settingsQuery.data.values.auth;
    return (
      mode !== auth.mode ||
      resetEnabled !== auth.password.resetEnabled ||
      mfaRequired !== auth.password.mfaRequired ||
      Number(minLength) !== auth.password.complexity.minLength ||
      requireUppercase !== auth.password.complexity.requireUppercase ||
      requireLowercase !== auth.password.complexity.requireLowercase ||
      requireNumber !== auth.password.complexity.requireNumber ||
      requireSymbol !== auth.password.complexity.requireSymbol ||
      Number(lockoutAttempts) !== auth.password.lockout.maxAttempts ||
      Number(lockoutSeconds) !== auth.password.lockout.durationSeconds ||
      provisioningMode !== auth.identityProvider.provisioningMode
    );
  }, [
    lockoutAttempts,
    lockoutSeconds,
    mfaRequired,
    minLength,
    mode,
    provisioningMode,
    requireLowercase,
    requireNumber,
    requireSymbol,
    requireUppercase,
    resetEnabled,
    settingsQuery.data,
  ]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved authentication policy changes.",
    shouldBypassNavigation: () => patchMutation.isPending,
  });

  if (!canRead) {
    return <SettingsAccessDenied returnHref={settingsPaths.home} />;
  }

  if (settingsQuery.isLoading) {
    return <SettingsDetailLayout title="Authentication" subtitle="Loading settings..." breadcrumbs={[{ label: "Settings", href: settingsPaths.home }, { label: "Organization" }, { label: "Authentication" }]}><p className="text-sm text-muted-foreground">Loading authentication settings...</p></SettingsDetailLayout>;
  }

  if (settingsQuery.isError || !settingsQuery.data) {
    return (
      <SettingsErrorState
        title="Authentication settings unavailable"
        message={normalizeSettingsError(settingsQuery.error, "Unable to load authentication settings.").message}
      />
    );
  }

  const settings = settingsQuery.data;
  const providers = providersQuery.data?.items ?? [];

  const savePolicy = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);

    const minLengthValue = toNumberOrNull(minLength);
    const maxAttemptsValue = toNumberOrNull(lockoutAttempts);
    const durationValue = toNumberOrNull(lockoutSeconds);

    if (minLengthValue == null || maxAttemptsValue == null || durationValue == null) {
      setErrorMessage("Password and lockout values must be valid numbers.");
      return;
    }

    try {
      await patchMutation.mutateAsync({
        revision: settings.revision,
        changes: {
          auth: {
            mode,
            password: {
              resetEnabled,
              mfaRequired,
              complexity: {
                minLength: minLengthValue,
                requireUppercase,
                requireLowercase,
                requireNumber,
                requireSymbol,
              },
              lockout: {
                maxAttempts: maxAttemptsValue,
                durationSeconds: durationValue,
              },
            },
            identityProvider: {
              provisioningMode,
            },
          },
        },
      });
      setSuccessMessage("Authentication policy updated.");
    } catch (error) {
      setErrorMessage(normalizeSettingsError(error, "Unable to update authentication policy.").message);
    }
  };

  return (
    <SettingsDetailLayout
      title="Authentication"
      subtitle="Configure password policy, sign-in mode, identity provider provisioning, and SSO integrations."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Authentication" },
      ]}
      actions={
        canManage ? (
          <Button
            onClick={(event) => {
              setSetupFlowMode("create");
              setSetupProviderId(null);
              setSetupReturnFocusTarget(event.currentTarget);
              setSetupFlowOpen(true);
            }}
          >
            Add provider
          </Button>
        ) : null
      }
      sections={AUTHENTICATION_SECTIONS}
      defaultSectionId="sign-in-mode"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}
      {scimTokenSecret ? (
        <Alert tone="success" heading="SCIM token created">
          Copy this token now: <strong>{scimTokenSecret}</strong>
        </Alert>
      ) : null}

      <SettingsDetailSection id="sign-in-mode" title="Sign-in mode">
        <FormField label="Authentication mode" required>
          <Select value={mode} onValueChange={(value) => setMode(value as typeof mode)}>
            <SelectTrigger disabled={!canManage || patchMutation.isPending}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="password_only">Password only</SelectItem>
              <SelectItem value="idp_only">Identity provider only</SelectItem>
              <SelectItem value="password_and_idp">Password and identity provider</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
      </SettingsDetailSection>

      <SettingsDetailSection id="password-policy" title="Password policy">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={resetEnabled} onChange={(event) => setResetEnabled(event.target.checked)} disabled={!canManage || patchMutation.isPending} />
          Allow password reset
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={mfaRequired} onChange={(event) => setMfaRequired(event.target.checked)} disabled={!canManage || patchMutation.isPending} />
          Require MFA for password sign-in
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Minimum length">
            <Input value={minLength} onChange={(event) => setMinLength(event.target.value)} disabled={!canManage || patchMutation.isPending} />
          </FormField>
          <FormField label="Lockout max attempts">
            <Input value={lockoutAttempts} onChange={(event) => setLockoutAttempts(event.target.value)} disabled={!canManage || patchMutation.isPending} />
          </FormField>
          <FormField label="Lockout duration seconds">
            <Input value={lockoutSeconds} onChange={(event) => setLockoutSeconds(event.target.value)} disabled={!canManage || patchMutation.isPending} />
          </FormField>
        </div>

        <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/20 p-3">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={requireUppercase} onChange={(event) => setRequireUppercase(event.target.checked)} disabled={!canManage || patchMutation.isPending} />Require uppercase</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={requireLowercase} onChange={(event) => setRequireLowercase(event.target.checked)} disabled={!canManage || patchMutation.isPending} />Require lowercase</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={requireNumber} onChange={(event) => setRequireNumber(event.target.checked)} disabled={!canManage || patchMutation.isPending} />Require number</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={requireSymbol} onChange={(event) => setRequireSymbol(event.target.checked)} disabled={!canManage || patchMutation.isPending} />Require symbol</label>
        </div>
      </SettingsDetailSection>

      <SettingsDetailSection id="provisioning" title="Provisioning">
        <FormField label="Identity provider provisioning mode">
          <Select value={provisioningMode} onValueChange={(value) => setProvisioningMode(value as typeof provisioningMode)}>
            <SelectTrigger disabled={!canManage || patchMutation.isPending}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="disabled">Disabled</SelectItem>
              <SelectItem value="jit">Just in time</SelectItem>
              <SelectItem value="scim">SCIM</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        {provisioningMode === "scim" ? (
          <div className="space-y-3 rounded-lg border border-border/70 bg-muted/20 p-4">
            <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
              <FormField label="Token name">
                <Input value={scimTokenName} onChange={(event) => setScimTokenName(event.target.value)} placeholder="Okta sync" disabled={!canManage || createScimTokenMutation.isPending} />
              </FormField>
              <Button
                disabled={!canManage || createScimTokenMutation.isPending || !scimTokenName.trim()}
                onClick={async () => {
                  setErrorMessage(null);
                  setSuccessMessage(null);
                  setScimTokenSecret(null);
                  try {
                    const created = await createScimTokenMutation.mutateAsync({ name: scimTokenName.trim() });
                    setScimTokenName("");
                    setScimTokenSecret(created.token);
                    setSuccessMessage("SCIM token created.");
                  } catch (error) {
                    setErrorMessage(normalizeSettingsError(error, "Unable to create SCIM token.").message);
                  }
                }}
              >
                Create token
              </Button>
            </div>

            <div className="overflow-hidden rounded-xl border border-border/70 bg-background">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Prefix</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(scimTokensQuery.data?.items ?? []).map((token) => (
                    <TableRow key={token.id}>
                      <TableCell>{token.name}</TableCell>
                      <TableCell>{token.prefix}</TableCell>
                      <TableCell>{new Date(token.createdAt).toLocaleString()}</TableCell>
                      <TableCell>
                        <Badge variant={token.revokedAt ? "outline" : "secondary"}>{token.revokedAt ? "Revoked" : "Active"}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={!canManage || Boolean(token.revokedAt) || revokeScimTokenMutation.isPending}
                          onClick={async () => {
                            setErrorMessage(null);
                            setSuccessMessage(null);
                            try {
                              await revokeScimTokenMutation.mutateAsync(token.id);
                              setSuccessMessage("SCIM token revoked.");
                            } catch (error) {
                              setErrorMessage(normalizeSettingsError(error, "Unable to revoke token.").message);
                            }
                          }}
                        >
                          Revoke
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        ) : null}
      </SettingsDetailSection>

      <SettingsDetailSection id="sso-providers" title="SSO providers">
        {providersQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading providers...</p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border/70">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Managed</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {providers.map((provider) => (
                  <TableRow key={provider.id}>
                    <TableCell>
                      <p className="font-medium text-foreground">{provider.label}</p>
                      <p className="text-xs text-muted-foreground">{provider.id}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant={provider.status === "active" ? "secondary" : "outline"}>{provider.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{provider.managedBy}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={!canManage || provider.locked}
                          onClick={(event) => {
                            setSetupFlowMode("edit");
                            setSetupProviderId(provider.id);
                            setSetupReturnFocusTarget(event.currentTarget);
                            setSetupFlowOpen(true);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={!canManage || provider.locked || updateProviderMutation.isPending}
                          onClick={async () => {
                            setErrorMessage(null);
                            setSuccessMessage(null);
                            try {
                              await updateProviderMutation.mutateAsync({
                                id: provider.id,
                                payload: { status: provider.status === "active" ? "disabled" : "active" },
                              });
                              setSuccessMessage("Provider status updated.");
                            } catch (error) {
                              setErrorMessage(normalizeSettingsError(error, "Unable to update provider.").message);
                            }
                          }}
                        >
                          {provider.status === "active" ? "Disable" : "Enable"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={!canManage || provider.locked || deleteProviderMutation.isPending}
                          onClick={() => setProviderToDelete(provider.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave={canManage}
        isSaving={patchMutation.isPending}
        onSave={() => {
          void savePolicy();
        }}
        onDiscard={() => {
          const auth = settings.values.auth;
          setMode(auth.mode);
          setResetEnabled(auth.password.resetEnabled);
          setMfaRequired(auth.password.mfaRequired);
          setMinLength(String(auth.password.complexity.minLength));
          setRequireUppercase(auth.password.complexity.requireUppercase);
          setRequireLowercase(auth.password.complexity.requireLowercase);
          setRequireNumber(auth.password.complexity.requireNumber);
          setRequireSymbol(auth.password.complexity.requireSymbol);
          setLockoutAttempts(String(auth.password.lockout.maxAttempts));
          setLockoutSeconds(String(auth.password.lockout.durationSeconds));
          setProvisioningMode(auth.identityProvider.provisioningMode);
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Authentication policy changes are pending"
      />

      <SsoSetupFlow
        open={setupFlowOpen}
        mode={setupFlowMode}
        provider={selectedSetupProvider}
        returnFocusTarget={setupReturnFocusTarget}
        canManage={canManage}
        isSubmitting={createProviderMutation.isPending || updateProviderMutation.isPending}
        isValidating={validateProviderMutation.isPending}
        onOpenChange={(nextOpen) => setSetupFlowOpen(nextOpen)}
        onValidate={(payload) => validateProviderMutation.mutateAsync(payload)}
        onCreate={async (payload) => {
          await createProviderMutation.mutateAsync(payload);
        }}
        onUpdate={async (id, payload) => {
          await updateProviderMutation.mutateAsync({ id, payload });
        }}
        onSuccess={(message) => {
          setSuccessMessage(message);
          setErrorMessage(null);
        }}
      />

      <ConfirmDialog
        open={Boolean(providerToDelete)}
        title="Delete provider?"
        description="Deleting this provider removes it from sign-in choices."
        confirmLabel="Delete provider"
        tone="danger"
        onCancel={() => setProviderToDelete(null)}
        onConfirm={async () => {
          if (!providerToDelete) return;
          setErrorMessage(null);
          setSuccessMessage(null);
          try {
            await deleteProviderMutation.mutateAsync(providerToDelete);
            setProviderToDelete(null);
            setSuccessMessage("Provider deleted.");
          } catch (error) {
            setErrorMessage(normalizeSettingsError(error, "Unable to delete provider.").message);
          }
        }}
        isConfirming={deleteProviderMutation.isPending}
      />
    </SettingsDetailLayout>
  );
}
