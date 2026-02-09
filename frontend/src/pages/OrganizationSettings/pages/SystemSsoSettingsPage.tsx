import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";

import { mapUiError } from "@/api/uiErrors";
import type { ProblemDetailsErrorMap } from "@/api/errors";
import type { AdminSettingsPatchRequest } from "@/api/admin/settings";
import type {
  SsoProviderCreateRequest,
  SsoProviderUpdateRequest,
  SsoProviderValidateRequest,
  SsoProviderValidationResponse,
} from "@/api/admin/sso";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import {
  useAdminSettingsQuery,
  useCreateSsoProviderMutation,
  usePatchAdminSettingsMutation,
  useSsoProvidersQuery,
  useUpdateSsoProviderMutation,
  useValidateSsoProviderMutation,
} from "@/hooks/admin";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SsoSetupFlow } from "@/features/sso-setup";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";
import { SettingsFieldRow } from "../components/SettingsFieldRow";
import { SettingsSaveBar } from "../components/SettingsSaveBar";
import { SettingsTechnicalDetails } from "../components/SettingsTechnicalDetails";
import { findRuntimeSettingFieldError, hasProblemCode } from "../components/runtimeSettingsUtils";

type FeedbackTone = "success" | "danger";
type FeedbackMessage = { tone: FeedbackTone; message: string };
type ProviderStatusAction = "enable" | "disable";
type AuthMode = "password_only" | "idp_only" | "password_and_idp";

export function SystemSsoSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const canManage = hasPermission("system.settings.manage");
  const canRead = hasPermission("system.settings.read") || canManage;

  const providersQuery = useSsoProvidersQuery({ enabled: canRead });
  const settingsQuery = useAdminSettingsQuery({ enabled: canRead });

  const createProvider = useCreateSsoProviderMutation();
  const updateProvider = useUpdateSsoProviderMutation();
  const validateProvider = useValidateSsoProviderMutation();
  const patchSettings = usePatchAdminSettingsMutation();

  const [feedback, setFeedback] = useState<FeedbackMessage | null>(null);
  const [settingsFieldErrors, setSettingsFieldErrors] = useState<ProblemDetailsErrorMap>({});
  const [syncedRevision, setSyncedRevision] = useState<number | null>(null);

  const [authMode, setAuthMode] = useState<AuthMode>("password_only");
  const [passwordResetEnabled, setPasswordResetEnabled] = useState(true);
  const [passwordMfaRequired, setPasswordMfaRequired] = useState(false);
  const [passwordMinLength, setPasswordMinLength] = useState("12");
  const [passwordRequireUppercase, setPasswordRequireUppercase] = useState(false);
  const [passwordRequireLowercase, setPasswordRequireLowercase] = useState(false);
  const [passwordRequireNumber, setPasswordRequireNumber] = useState(false);
  const [passwordRequireSymbol, setPasswordRequireSymbol] = useState(false);
  const [passwordLockoutMaxAttempts, setPasswordLockoutMaxAttempts] = useState("5");
  const [passwordLockoutDurationSeconds, setPasswordLockoutDurationSeconds] = useState("300");
  const [idpJitProvisioningEnabled, setIdpJitProvisioningEnabled] = useState(true);

  const [setupFlowOpen, setSetupFlowOpen] = useState(false);
  const [setupFlowMode, setSetupFlowMode] = useState<"create" | "edit">("create");
  const [setupProviderId, setSetupProviderId] = useState<string | null>(null);
  const [setupReturnFocusTarget, setSetupReturnFocusTarget] = useState<HTMLElement | null>(null);
  const [statusTargetProviderId, setStatusTargetProviderId] = useState<string | null>(null);

  const providers = providersQuery.data?.items ?? [];
  const sortedProviders = useMemo(
    () =>
      [...providers].sort((left, right) => {
        if (left.status !== right.status) {
          return left.status === "active" ? -1 : 1;
        }
        return left.label.localeCompare(right.label);
      }),
    [providers],
  );
  const selectedSetupProvider = useMemo(
    () => sortedProviders.find((provider) => provider.id === setupProviderId),
    [setupProviderId, sortedProviders],
  );
  const statusActionTarget = useMemo(
    () => sortedProviders.find((provider) => provider.id === statusTargetProviderId) ?? null,
    [sortedProviders, statusTargetProviderId],
  );
  const activeProviderCount = useMemo(
    () => sortedProviders.filter((provider) => provider.status === "active").length,
    [sortedProviders],
  );

  const hasUnsavedAuthSetting = useMemo(() => {
    if (!settingsQuery.data) {
      return false;
    }
    const saved = settingsQuery.data.values.auth;
    return (
      authMode !== saved.mode ||
      passwordResetEnabled !== saved.password.resetEnabled ||
      passwordMfaRequired !== saved.password.mfaRequired ||
      Number(passwordMinLength) !== saved.password.complexity.minLength ||
      passwordRequireUppercase !== saved.password.complexity.requireUppercase ||
      passwordRequireLowercase !== saved.password.complexity.requireLowercase ||
      passwordRequireNumber !== saved.password.complexity.requireNumber ||
      passwordRequireSymbol !== saved.password.complexity.requireSymbol ||
      Number(passwordLockoutMaxAttempts) !== saved.password.lockout.maxAttempts ||
      Number(passwordLockoutDurationSeconds) !== saved.password.lockout.durationSeconds ||
      idpJitProvisioningEnabled !== saved.identityProvider.jitProvisioningEnabled
    );
  }, [
    authMode,
    idpJitProvisioningEnabled,
    passwordLockoutDurationSeconds,
    passwordLockoutMaxAttempts,
    passwordMfaRequired,
    passwordMinLength,
    passwordRequireLowercase,
    passwordRequireNumber,
    passwordRequireSymbol,
    passwordRequireUppercase,
    passwordResetEnabled,
    settingsQuery.data,
  ]);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }

    const shouldSyncDraft =
      syncedRevision === null || (!hasUnsavedAuthSetting && syncedRevision !== settingsQuery.data.revision);
    if (!shouldSyncDraft) {
      return;
    }

    const saved = settingsQuery.data.values.auth;
    setAuthMode(saved.mode);
    setPasswordResetEnabled(saved.password.resetEnabled);
    setPasswordMfaRequired(saved.password.mfaRequired);
    setPasswordMinLength(String(saved.password.complexity.minLength));
    setPasswordRequireUppercase(saved.password.complexity.requireUppercase);
    setPasswordRequireLowercase(saved.password.complexity.requireLowercase);
    setPasswordRequireNumber(saved.password.complexity.requireNumber);
    setPasswordRequireSymbol(saved.password.complexity.requireSymbol);
    setPasswordLockoutMaxAttempts(String(saved.password.lockout.maxAttempts));
    setPasswordLockoutDurationSeconds(String(saved.password.lockout.durationSeconds));
    setIdpJitProvisioningEnabled(saved.identityProvider.jitProvisioningEnabled);
    setSettingsFieldErrors({});
    setSyncedRevision(settingsQuery.data.revision);
  }, [hasUnsavedAuthSetting, settingsQuery.data, syncedRevision]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedAuthSetting,
    message: "You have unsaved changes in Authentication policy. Are you sure you want to leave?",
    shouldBypassNavigation: () => patchSettings.isPending,
  });

  const authMeta = settingsQuery.data?.meta.auth;
  const modeLocked = Boolean(authMeta?.mode.lockedByEnv);
  const passwordResetLocked = Boolean(authMeta?.password.resetEnabled.lockedByEnv);
  const passwordMfaLocked = Boolean(authMeta?.password.mfaRequired.lockedByEnv);
  const minLengthLocked = Boolean(authMeta?.password.complexity.minLength.lockedByEnv);
  const requireUppercaseLocked = Boolean(authMeta?.password.complexity.requireUppercase.lockedByEnv);
  const requireLowercaseLocked = Boolean(authMeta?.password.complexity.requireLowercase.lockedByEnv);
  const requireNumberLocked = Boolean(authMeta?.password.complexity.requireNumber.lockedByEnv);
  const requireSymbolLocked = Boolean(authMeta?.password.complexity.requireSymbol.lockedByEnv);
  const lockoutAttemptsLocked = Boolean(authMeta?.password.lockout.maxAttempts.lockedByEnv);
  const lockoutDurationLocked = Boolean(authMeta?.password.lockout.durationSeconds.lockedByEnv);
  const idpJitLocked = Boolean(authMeta?.identityProvider.jitProvisioningEnabled.lockedByEnv);

  const modeError = findRuntimeSettingFieldError(settingsFieldErrors, "auth.mode");
  const passwordResetError = findRuntimeSettingFieldError(settingsFieldErrors, "auth.password.resetEnabled");
  const passwordMfaError = findRuntimeSettingFieldError(settingsFieldErrors, "auth.password.mfaRequired");
  const minLengthError = findRuntimeSettingFieldError(settingsFieldErrors, "auth.password.complexity.minLength");
  const requireUppercaseError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.password.complexity.requireUppercase",
  );
  const requireLowercaseError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.password.complexity.requireLowercase",
  );
  const requireNumberError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.password.complexity.requireNumber",
  );
  const requireSymbolError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.password.complexity.requireSymbol",
  );
  const lockoutAttemptsError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.password.lockout.maxAttempts",
  );
  const lockoutDurationError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.password.lockout.durationSeconds",
  );
  const idpJitError = findRuntimeSettingFieldError(
    settingsFieldErrors,
    "auth.identityProvider.jitProvisioningEnabled",
  );

  const hasEditableAuthSettingChanges = useMemo(() => {
    if (!settingsQuery.data) {
      return false;
    }
    const saved = settingsQuery.data.values.auth;
    return (
      (!modeLocked && authMode !== saved.mode) ||
      (!passwordResetLocked && passwordResetEnabled !== saved.password.resetEnabled) ||
      (!passwordMfaLocked && passwordMfaRequired !== saved.password.mfaRequired) ||
      (!minLengthLocked && Number(passwordMinLength) !== saved.password.complexity.minLength) ||
      (!requireUppercaseLocked &&
        passwordRequireUppercase !== saved.password.complexity.requireUppercase) ||
      (!requireLowercaseLocked &&
        passwordRequireLowercase !== saved.password.complexity.requireLowercase) ||
      (!requireNumberLocked && passwordRequireNumber !== saved.password.complexity.requireNumber) ||
      (!requireSymbolLocked && passwordRequireSymbol !== saved.password.complexity.requireSymbol) ||
      (!lockoutAttemptsLocked && Number(passwordLockoutMaxAttempts) !== saved.password.lockout.maxAttempts) ||
      (!lockoutDurationLocked &&
        Number(passwordLockoutDurationSeconds) !== saved.password.lockout.durationSeconds) ||
      (!idpJitLocked &&
        idpJitProvisioningEnabled !== saved.identityProvider.jitProvisioningEnabled)
    );
  }, [
    authMode,
    idpJitLocked,
    idpJitProvisioningEnabled,
    lockoutAttemptsLocked,
    lockoutDurationLocked,
    minLengthLocked,
    modeLocked,
    passwordLockoutDurationSeconds,
    passwordLockoutMaxAttempts,
    passwordMfaLocked,
    passwordMfaRequired,
    passwordMinLength,
    passwordRequireLowercase,
    passwordRequireNumber,
    passwordRequireSymbol,
    passwordRequireUppercase,
    passwordResetEnabled,
    passwordResetLocked,
    requireLowercaseLocked,
    requireNumberLocked,
    requireSymbolLocked,
    requireUppercaseLocked,
    settingsQuery.data,
  ]);

  const resetSettingsDraft = () => {
    if (!settingsQuery.data) {
      return;
    }
    const saved = settingsQuery.data.values.auth;
    setAuthMode(saved.mode);
    setPasswordResetEnabled(saved.password.resetEnabled);
    setPasswordMfaRequired(saved.password.mfaRequired);
    setPasswordMinLength(String(saved.password.complexity.minLength));
    setPasswordRequireUppercase(saved.password.complexity.requireUppercase);
    setPasswordRequireLowercase(saved.password.complexity.requireLowercase);
    setPasswordRequireNumber(saved.password.complexity.requireNumber);
    setPasswordRequireSymbol(saved.password.complexity.requireSymbol);
    setPasswordLockoutMaxAttempts(String(saved.password.lockout.maxAttempts));
    setPasswordLockoutDurationSeconds(String(saved.password.lockout.durationSeconds));
    setIdpJitProvisioningEnabled(saved.identityProvider.jitProvisioningEnabled);
    setSettingsFieldErrors({});
    setSyncedRevision(settingsQuery.data.revision);
    setFeedback(null);
  };

  const modeConstraintError =
    authMode === "idp_only" && activeProviderCount < 1
      ? "Add and activate at least one provider before requiring identity provider sign-in."
      : null;

  const handleSaveSettings = async () => {
    setFeedback(null);
    setSettingsFieldErrors({});
    if (!settingsQuery.data) {
      return;
    }

    const saved = settingsQuery.data.values.auth;
    const authChanges: NonNullable<AdminSettingsPatchRequest["changes"]["auth"]> = {};
    const passwordChanges: NonNullable<NonNullable<AdminSettingsPatchRequest["changes"]["auth"]>["password"]> = {};
    const complexityChanges: NonNullable<
      NonNullable<NonNullable<AdminSettingsPatchRequest["changes"]["auth"]>["password"]>["complexity"]
    > = {};
    const lockoutChanges: NonNullable<
      NonNullable<NonNullable<AdminSettingsPatchRequest["changes"]["auth"]>["password"]>["lockout"]
    > = {};

    if (!modeLocked && authMode !== saved.mode) {
      authChanges.mode = authMode;
    }
    if (!passwordResetLocked && passwordResetEnabled !== saved.password.resetEnabled) {
      passwordChanges.resetEnabled = passwordResetEnabled;
    }
    if (!passwordMfaLocked && passwordMfaRequired !== saved.password.mfaRequired) {
      passwordChanges.mfaRequired = passwordMfaRequired;
    }
    if (!minLengthLocked && Number(passwordMinLength) !== saved.password.complexity.minLength) {
      complexityChanges.minLength = Number(passwordMinLength);
    }
    if (
      !requireUppercaseLocked &&
      passwordRequireUppercase !== saved.password.complexity.requireUppercase
    ) {
      complexityChanges.requireUppercase = passwordRequireUppercase;
    }
    if (
      !requireLowercaseLocked &&
      passwordRequireLowercase !== saved.password.complexity.requireLowercase
    ) {
      complexityChanges.requireLowercase = passwordRequireLowercase;
    }
    if (!requireNumberLocked && passwordRequireNumber !== saved.password.complexity.requireNumber) {
      complexityChanges.requireNumber = passwordRequireNumber;
    }
    if (!requireSymbolLocked && passwordRequireSymbol !== saved.password.complexity.requireSymbol) {
      complexityChanges.requireSymbol = passwordRequireSymbol;
    }
    if (
      !lockoutAttemptsLocked &&
      Number(passwordLockoutMaxAttempts) !== saved.password.lockout.maxAttempts
    ) {
      lockoutChanges.maxAttempts = Number(passwordLockoutMaxAttempts);
    }
    if (
      !lockoutDurationLocked &&
      Number(passwordLockoutDurationSeconds) !== saved.password.lockout.durationSeconds
    ) {
      lockoutChanges.durationSeconds = Number(passwordLockoutDurationSeconds);
    }
    if (
      !idpJitLocked &&
      idpJitProvisioningEnabled !== saved.identityProvider.jitProvisioningEnabled
    ) {
      authChanges.identityProvider = {
        ...(authChanges.identityProvider ?? {}),
        jitProvisioningEnabled: idpJitProvisioningEnabled,
      };
    }

    if (Object.keys(complexityChanges).length > 0) {
      passwordChanges.complexity = complexityChanges;
    }
    if (Object.keys(lockoutChanges).length > 0) {
      passwordChanges.lockout = lockoutChanges;
    }
    if (Object.keys(passwordChanges).length > 0) {
      authChanges.password = passwordChanges;
    }
    if (Object.keys(authChanges).length === 0) {
      return;
    }

    try {
      const updated = await patchSettings.mutateAsync({
        revision: settingsQuery.data.revision,
        changes: { auth: authChanges },
      });
      setSyncedRevision(updated.revision);
      setFeedback({ tone: "success", message: "Authentication policy updated." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to update authentication policy.",
        statusMessages: {
          409: "Settings changed while you were editing. Review your draft and save again.",
        },
      });
      setFeedback({ tone: "danger", message: mapped.message });
      setSettingsFieldErrors(mapped.fieldErrors);
      if (hasProblemCode(error, "settings_revision_conflict")) {
        await settingsQuery.refetch();
      }
    }
  };

  const openCreateFlow = (returnFocusTarget?: HTMLElement | null) => {
    setFeedback(null);
    setSetupFlowMode("create");
    setSetupProviderId(null);
    setSetupReturnFocusTarget(returnFocusTarget ?? null);
    setSetupFlowOpen(true);
  };

  const openEditFlow = (providerId: string, returnFocusTarget?: HTMLElement | null) => {
    setFeedback(null);
    setSetupFlowMode("edit");
    setSetupProviderId(providerId);
    setSetupReturnFocusTarget(returnFocusTarget ?? null);
    setSetupFlowOpen(true);
  };

  const handleFlowOpenChange = (nextOpen: boolean) => {
    setSetupFlowOpen(nextOpen);
    if (!nextOpen) {
      setSetupProviderId(null);
    }
  };

  const statusAction: ProviderStatusAction | null = statusActionTarget
    ? statusActionTarget.status === "active"
      ? "disable"
      : "enable"
    : null;

  const handleProviderStatusAction = async () => {
    if (!statusActionTarget || !statusAction) {
      return;
    }

    setFeedback(null);
    try {
      await updateProvider.mutateAsync({
        id: statusActionTarget.id,
        payload: {
          status: statusAction === "disable" ? "disabled" : "active",
        },
      });
      const statusVerb = statusAction === "disable" ? "disabled" : "enabled";
      setFeedback({
        tone: "success",
        message: `Provider ${statusActionTarget.label} ${statusVerb}.`,
      });
      if (setupProviderId === statusActionTarget.id) {
        handleFlowOpenChange(false);
      }
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback:
          statusAction === "disable"
            ? "Unable to disable provider."
            : "Unable to enable provider.",
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setStatusTargetProviderId(null);
    }
  };

  const isSavingSettings = patchSettings.isPending;
  const isMutatingProviders = createProvider.isPending || updateProvider.isPending;
  const canSaveSettings = hasEditableAuthSettingChanges && !modeConstraintError;

  const hasEnvLocks =
    modeLocked ||
    passwordResetLocked ||
    passwordMfaLocked ||
    minLengthLocked ||
    requireUppercaseLocked ||
    requireLowercaseLocked ||
    requireNumberLocked ||
    requireSymbolLocked ||
    lockoutAttemptsLocked ||
    lockoutDurationLocked ||
    idpJitLocked;

  const passwordControlsApplicable = authMode !== "idp_only";
  const idpControlsApplicable = authMode !== "password_only";

  if (!canRead) {
    return <Alert tone="danger">You do not have permission to access authentication settings.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {providersQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(providersQuery.error, { fallback: "Unable to load authentication providers." }).message}
        </Alert>
      ) : null}
      {settingsQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(settingsQuery.error, { fallback: "Unable to load authentication settings." }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="Authentication methods"
        description="Configure password and identity provider sign-in behaviors."
      >
        <section className="space-y-4">
          <h3 className="text-base font-semibold text-foreground">Password sign-in</h3>
          <div className="space-y-3">
            <SettingsFieldRow
              label="Password reset enabled"
              description="Allow public forgot-password and reset-password flows."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.resetEnabled}
              error={passwordResetError}
            >
              <ToggleControl
                checked={passwordResetEnabled}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  passwordResetLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordResetEnabled}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Password MFA required"
              description="Require users with password sessions to complete MFA setup before protected access."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.mfaRequired}
              error={passwordMfaError}
            >
              <ToggleControl
                checked={passwordMfaRequired}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  passwordMfaLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordMfaRequired}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Minimum password length"
              description="Minimum number of characters required for password sign-in."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.complexity.minLength}
              error={minLengthError}
            >
              <NumericInputControl
                value={passwordMinLength}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  minLengthLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordMinLength}
                min={8}
                max={128}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Require uppercase letter"
              description="Require at least one uppercase letter in passwords."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.complexity.requireUppercase}
              error={requireUppercaseError}
            >
              <ToggleControl
                checked={passwordRequireUppercase}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  requireUppercaseLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordRequireUppercase}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Require lowercase letter"
              description="Require at least one lowercase letter in passwords."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.complexity.requireLowercase}
              error={requireLowercaseError}
            >
              <ToggleControl
                checked={passwordRequireLowercase}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  requireLowercaseLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordRequireLowercase}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Require number"
              description="Require at least one numeric character in passwords."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.complexity.requireNumber}
              error={requireNumberError}
            >
              <ToggleControl
                checked={passwordRequireNumber}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  requireNumberLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordRequireNumber}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Require symbol"
              description="Require at least one symbol character in passwords."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.complexity.requireSymbol}
              error={requireSymbolError}
            >
              <ToggleControl
                checked={passwordRequireSymbol}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  requireSymbolLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordRequireSymbol}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Lockout max attempts"
              description="Lock an account after this many failed password attempts."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.lockout.maxAttempts}
              error={lockoutAttemptsError}
            >
              <NumericInputControl
                value={passwordLockoutMaxAttempts}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  lockoutAttemptsLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordLockoutMaxAttempts}
                min={1}
                max={20}
              />
            </SettingsFieldRow>

            <SettingsFieldRow
              label="Lockout duration (seconds)"
              description="Duration of account lockout after reaching max attempts."
              hint={
                passwordControlsApplicable
                  ? undefined
                  : "Password sign-in settings don't apply while identity provider-only mode is selected."
              }
              meta={authMeta?.password.lockout.durationSeconds}
              error={lockoutDurationError}
            >
              <NumericInputControl
                value={passwordLockoutDurationSeconds}
                disabled={
                  !canManage ||
                  isSavingSettings ||
                  settingsQuery.isLoading ||
                  lockoutDurationLocked ||
                  !passwordControlsApplicable
                }
                onChange={setPasswordLockoutDurationSeconds}
                min={30}
                max={86400}
              />
            </SettingsFieldRow>
          </div>
        </section>

        <section className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-foreground">Identity provider sign-in (SSO)</h3>
            {canManage ? (
              <Button
                type="button"
                onClick={(event) => openCreateFlow(event.currentTarget)}
                disabled={isMutatingProviders}
              >
                {providers.length === 0 ? "Set up SSO" : "Add provider"}
              </Button>
            ) : null}
          </div>

          {providers.length === 0 ? (
            <Alert tone="warning" icon={<AlertTriangle className="h-4 w-4" />}>
              No providers configured yet. Set up and validate a provider before requiring identity provider sign-in.
            </Alert>
          ) : (
            <ResponsiveAdminTable
              items={sortedProviders}
              getItemKey={(provider) => provider.id}
              mobileListLabel="Authentication providers"
              desktopTable={
                <div className="overflow-hidden rounded-xl border border-border">
                  <Table>
                    <TableHeader>
                      <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        <TableHead className="px-4">Provider</TableHead>
                        <TableHead className="px-4">Domains</TableHead>
                        <TableHead className="px-4">Status</TableHead>
                        <TableHead className="px-4 text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedProviders.map((provider) => (
                        <TableRow key={provider.id} className="text-sm text-foreground">
                          <TableCell className="space-y-1 px-4 py-3">
                            <p className="font-semibold text-foreground">{provider.label}</p>
                            <p className="font-mono text-xs text-muted-foreground">{provider.id}</p>
                            <p className="truncate text-xs text-muted-foreground">{provider.issuer}</p>
                          </TableCell>
                          <TableCell className="px-4 py-3 text-xs text-muted-foreground">
                            {(provider.domains ?? []).length > 0
                              ? provider.domains.join(", ")
                              : "No domain restrictions"}
                          </TableCell>
                          <TableCell className="px-4 py-3">
                            <Badge variant={provider.status === "active" ? "secondary" : "outline"}>
                              {provider.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="px-4 py-3 text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                disabled={!canManage || isMutatingProviders}
                                onClick={(event) => openEditFlow(provider.id, event.currentTarget)}
                              >
                                Edit setup
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={!canManage || isMutatingProviders}
                                onClick={() => setStatusTargetProviderId(provider.id)}
                              >
                                {provider.status === "active" ? "Disable" : "Enable"}
                              </Button>
                            </div>
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
                    <p className="break-all text-xs text-muted-foreground">{provider.issuer}</p>
                  </div>
                  <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                    <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Domains</dt>
                    <dd className="text-muted-foreground">
                      {(provider.domains ?? []).length > 0
                        ? provider.domains.join(", ")
                        : "No domain restrictions"}
                    </dd>
                    <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                    <dd>
                      <Badge variant={provider.status === "active" ? "secondary" : "outline"}>
                        {provider.status}
                      </Badge>
                    </dd>
                  </dl>
                  <div className="flex justify-end gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={!canManage || isMutatingProviders}
                      onClick={(event) => openEditFlow(provider.id, event.currentTarget)}
                    >
                      Edit setup
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={!canManage || isMutatingProviders}
                      onClick={() => setStatusTargetProviderId(provider.id)}
                    >
                      {provider.status === "active" ? "Disable" : "Enable"}
                    </Button>
                  </div>
                </>
              )}
            />
          )}

          <SettingsFieldRow
            label="JIT provisioning"
            description="Create user records automatically when a valid identity signs in."
            hint={
              idpControlsApplicable
                ? undefined
                : "Identity provider settings don't apply while password-only mode is selected."
            }
            meta={authMeta?.identityProvider.jitProvisioningEnabled}
            error={idpJitError}
          >
            <ToggleControl
              checked={idpJitProvisioningEnabled}
              disabled={
                !canManage ||
                isSavingSettings ||
                settingsQuery.isLoading ||
                idpJitLocked ||
                !idpControlsApplicable
              }
              onChange={setIdpJitProvisioningEnabled}
            />
          </SettingsFieldRow>
        </section>
      </SettingsSection>

      <SettingsSection
        title="Authentication mode"
        description="Choose the effective sign-in rule for the workspace."
      >
        <SettingsFieldRow
          label="Mode"
          description="This controls who can use password sign-in versus identity provider sign-in."
          hint={modeConstraintError ?? undefined}
          meta={authMeta?.mode}
          error={modeError}
        >
          <fieldset className="space-y-2" disabled={!canManage || isSavingSettings || settingsQuery.isLoading || modeLocked}>
            <RadioOption
              name="auth-mode"
              value="password_only"
              checked={authMode === "password_only"}
              label="Password sign-in only"
              description="Only password sign-in is available."
              onChange={() => setAuthMode("password_only")}
            />
            <RadioOption
              name="auth-mode"
              value="idp_only"
              checked={authMode === "idp_only"}
              label="Identity provider sign-in only"
              description="Organization members must sign in with identity providers. Global admins keep password + MFA access."
              disabled={activeProviderCount < 1 && authMode !== "idp_only"}
              onChange={() => setAuthMode("idp_only")}
            />
            <RadioOption
              name="auth-mode"
              value="password_and_idp"
              checked={authMode === "password_and_idp"}
              label="Password + identity provider sign-in"
              description="Both password and identity provider sign-in are available."
              onChange={() => setAuthMode("password_and_idp")}
            />
          </fieldset>
        </SettingsFieldRow>

        {hasEnvLocks ? (
          <Alert tone="info">
            Some settings are managed by environment variables and are read-only here.
          </Alert>
        ) : null}

        <SettingsTechnicalDetails
          settings={settingsQuery.data}
          isLoading={settingsQuery.isLoading}
          onRefresh={() => settingsQuery.refetch()}
        />
      </SettingsSection>

      <SettingsSaveBar
        visible={hasUnsavedAuthSetting}
        canManage={canManage}
        isSaving={isSavingSettings}
        canSave={canSaveSettings}
        onSave={handleSaveSettings}
        onDiscard={resetSettingsDraft}
        message="Unsaved authentication policy changes."
      />

      <SsoSetupFlow
        open={setupFlowOpen}
        mode={setupFlowMode}
        provider={setupFlowMode === "edit" ? selectedSetupProvider : undefined}
        returnFocusTarget={setupReturnFocusTarget}
        canManage={canManage}
        isSubmitting={createProvider.isPending || updateProvider.isPending}
        isValidating={validateProvider.isPending}
        onOpenChange={handleFlowOpenChange}
        onValidate={async (payload: SsoProviderValidateRequest): Promise<SsoProviderValidationResponse> =>
          validateProvider.mutateAsync(payload)
        }
        onCreate={async (payload: SsoProviderCreateRequest): Promise<void> => {
          await createProvider.mutateAsync(payload);
        }}
        onUpdate={async (id: string, payload: SsoProviderUpdateRequest): Promise<void> => {
          await updateProvider.mutateAsync({ id, payload });
        }}
        onSuccess={(message) => setFeedback({ tone: "success", message })}
      />

      <ConfirmDialog
        open={Boolean(statusActionTarget)}
        title={
          statusActionTarget
            ? statusAction === "disable"
              ? `Disable ${statusActionTarget.label}?`
              : `Enable ${statusActionTarget.label}?`
            : "Update provider status?"
        }
        description={
          statusAction === "disable"
            ? "Users won't be able to sign in with this provider while it's disabled. You can enable it again anytime."
            : "Users can sign in with this provider as soon as it's enabled."
        }
        confirmLabel={statusAction === "disable" ? "Disable provider" : "Enable provider"}
        tone={statusAction === "disable" ? "danger" : "default"}
        isConfirming={updateProvider.isPending}
        onCancel={() => setStatusTargetProviderId(null)}
        onConfirm={() => {
          void handleProviderStatusAction();
        }}
      />
    </div>
  );
}

function ToggleControl({
  checked,
  disabled,
  onChange,
}: {
  readonly checked: boolean;
  readonly disabled: boolean;
  readonly onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-foreground">
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-border"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
      />
      <span>{checked ? "Enabled" : "Disabled"}</span>
    </label>
  );
}

function NumericInputControl({
  value,
  disabled,
  onChange,
  min,
  max,
}: {
  readonly value: string;
  readonly disabled: boolean;
  readonly onChange: (next: string) => void;
  readonly min: number;
  readonly max: number;
}) {
  return (
    <Input
      type="number"
      min={min}
      max={max}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      className="max-w-[220px]"
    />
  );
}

function RadioOption({
  name,
  value,
  checked,
  label,
  description,
  disabled = false,
  onChange,
}: {
  readonly name: string;
  readonly value: string;
  readonly checked: boolean;
  readonly label: string;
  readonly description: string;
  readonly disabled?: boolean;
  readonly onChange: () => void;
}) {
  const inputId = `${name}-${value}`;
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border/70 bg-background px-3 py-2.5 text-sm">
      <input
        id={inputId}
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="mt-1 h-4 w-4"
      />
      <label htmlFor={inputId} className="space-y-0.5">
        <span className="block font-medium text-foreground">{label}</span>
        <span className="block text-muted-foreground">{description}</span>
      </label>
    </div>
  );
}
