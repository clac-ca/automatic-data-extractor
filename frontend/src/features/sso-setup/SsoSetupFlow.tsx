import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, ShieldCheck } from "lucide-react";

import { mapUiError } from "@/api/uiErrors";
import type {
  SsoProviderAdmin,
  SsoProviderCreateRequest,
  SsoProviderUpdateRequest,
  SsoProviderValidateRequest,
  SsoProviderValidationResponse,
} from "@/api/admin/sso";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { hasProblemCode } from "@/pages/OrganizationSettings/components/runtimeSettingsUtils";

type WizardStep = "intro" | "basics" | "credentials" | "test" | "review";
type ProviderStatus = SsoProviderAdmin["status"];
type FeedbackTone = "success" | "danger" | "info";

type ProviderDraft = {
  id: string;
  label: string;
  issuer: string;
  clientId: string;
  clientSecret: string;
  status: ProviderStatus;
  domainsText: string;
};

type FieldErrors = Partial<Record<"id" | "label" | "issuer" | "clientId" | "clientSecret" | "domains", string>>;
type FeedbackMessage = { tone: FeedbackTone; message: string } | null;

const PROVIDER_ID_PATTERN = /^[a-z0-9][a-z0-9-_]{2,63}$/;
const DOMAIN_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/i;
const STEP_ORDER: readonly WizardStep[] = ["intro", "basics", "credentials", "test", "review"];

const STEP_LABELS: Record<WizardStep, string> = {
  intro: "Welcome",
  basics: "Basics",
  credentials: "Credentials",
  test: "Test",
  review: "Review",
};

function createInitialDraft(mode: "create" | "edit", provider?: SsoProviderAdmin): ProviderDraft {
  if (mode === "edit" && provider) {
    return {
      id: provider.id,
      label: provider.label,
      issuer: provider.issuer,
      clientId: provider.clientId,
      clientSecret: "",
      status: provider.status,
      domainsText: (provider.domains ?? []).join(", "),
    };
  }

  return {
    id: "",
    label: "",
    issuer: "",
    clientId: "",
    clientSecret: "",
    status: "active",
    domainsText: "",
  };
}

function normalizeIssuer(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function normalizeDomains(value: string): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const raw of value.split(",")) {
    const entry = raw.trim().toLowerCase();
    if (!entry || seen.has(entry)) {
      continue;
    }
    seen.add(entry);
    normalized.push(entry);
  }
  return normalized;
}

function parseInvalidDomain(value: string): string | null {
  const entries = value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  const invalid = entries.find((entry) => !DOMAIN_PATTERN.test(entry));
  return invalid ?? null;
}

function validateBasics(mode: "create" | "edit", draft: ProviderDraft): FieldErrors {
  const errors: FieldErrors = {};

  if (mode === "create") {
    const providerId = draft.id.trim();
    if (!providerId) {
      errors.id = "Provider ID is required.";
    } else if (!PROVIDER_ID_PATTERN.test(providerId)) {
      errors.id = "Use lowercase letters, numbers, dashes, or underscores (3-64 chars).";
    }
  }

  if (!draft.label.trim()) {
    errors.label = "Label is required.";
  }

  const invalidDomain = parseInvalidDomain(draft.domainsText);
  if (invalidDomain) {
    errors.domains = `Invalid domain: ${invalidDomain}`;
  }

  return errors;
}

function validateCredentials(draft: ProviderDraft, requireSecret: boolean): FieldErrors {
  const errors: FieldErrors = {};

  const issuer = normalizeIssuer(draft.issuer);
  if (!issuer) {
    errors.issuer = "Issuer is required.";
  } else {
    try {
      const parsed = new URL(issuer);
      if (parsed.protocol !== "https:") {
        errors.issuer = "Issuer must be an https URL.";
      }
    } catch {
      errors.issuer = "Issuer must be a valid URL.";
    }
  }

  if (!draft.clientId.trim()) {
    errors.clientId = "Client ID is required.";
  }

  if (requireSecret && !draft.clientSecret.trim()) {
    errors.clientSecret = "Client secret is required to test the provider connection.";
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

function requiresConnectionValidation(
  mode: "create" | "edit",
  provider: SsoProviderAdmin | undefined,
  draft: ProviderDraft,
): boolean {
  if (draft.status !== "active") {
    return false;
  }
  if (mode === "create" || !provider) {
    return true;
  }
  if (provider.status !== "active") {
    return true;
  }

  return (
    normalizeIssuer(draft.issuer) !== normalizeIssuer(provider.issuer) ||
    draft.clientId.trim() !== provider.clientId.trim() ||
    draft.clientSecret.trim().length > 0
  );
}

function previousStep(step: WizardStep): WizardStep {
  const index = STEP_ORDER.indexOf(step);
  return STEP_ORDER[Math.max(index - 1, 0)];
}

function stepIndex(step: WizardStep): number {
  return STEP_ORDER.indexOf(step);
}

interface SsoSetupFlowProps {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly provider?: SsoProviderAdmin;
  readonly returnFocusTarget?: HTMLElement | null;
  readonly canManage: boolean;
  readonly isSubmitting: boolean;
  readonly isValidating: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onValidate: (
    payload: SsoProviderValidateRequest,
  ) => Promise<SsoProviderValidationResponse>;
  readonly onCreate: (payload: SsoProviderCreateRequest) => Promise<void>;
  readonly onUpdate: (id: string, payload: SsoProviderUpdateRequest) => Promise<void>;
  readonly onSuccess?: (message: string) => void;
}

export function SsoSetupFlow({
  open,
  mode,
  provider,
  returnFocusTarget,
  canManage,
  isSubmitting,
  isValidating,
  onOpenChange,
  onValidate,
  onCreate,
  onUpdate,
  onSuccess,
}: SsoSetupFlowProps) {
  const [step, setStep] = useState<WizardStep>("intro");
  const [draft, setDraft] = useState<ProviderDraft>(() => createInitialDraft("create"));
  const [initialDraft, setInitialDraft] = useState<ProviderDraft>(() =>
    createInitialDraft("create"),
  );
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [feedback, setFeedback] = useState<FeedbackMessage>(null);
  const [validationResult, setValidationResult] =
    useState<SsoProviderValidationResponse | null>(null);
  const [validatedSignature, setValidatedSignature] = useState<string | null>(null);
  const [showDiscardInlineConfirm, setShowDiscardInlineConfirm] = useState(false);

  const missingProvider = mode === "edit" && !provider;

  useEffect(() => {
    if (!open) {
      return;
    }
    const next = createInitialDraft(mode, provider);
    setDraft(next);
    setInitialDraft(next);
    setFieldErrors({});
    setFeedback(null);
    setValidationResult(null);
    setValidatedSignature(null);
    setShowDiscardInlineConfirm(false);
    setStep("intro");
  }, [mode, open, provider]);

  const requiresValidation = useMemo(
    () => requiresConnectionValidation(mode, provider, draft),
    [draft, mode, provider],
  );
  const secretRequiredForValidation = requiresValidation && !draft.clientSecret.trim();

  const validationSignature = useMemo(
    () =>
      `${normalizeIssuer(draft.issuer)}|${draft.clientId.trim()}|${draft.clientSecret.trim()}`,
    [draft.clientId, draft.clientSecret, draft.issuer],
  );
  const validationCurrent =
    !requiresValidation ||
    (validationResult !== null && validatedSignature === validationSignature);

  const normalizedDomains = useMemo(() => normalizeDomains(draft.domainsText), [draft.domainsText]);

  const isDirty = useMemo(() => {
    return (
      draft.id !== initialDraft.id ||
      draft.label !== initialDraft.label ||
      draft.issuer !== initialDraft.issuer ||
      draft.clientId !== initialDraft.clientId ||
      draft.clientSecret !== initialDraft.clientSecret ||
      draft.status !== initialDraft.status ||
      draft.domainsText !== initialDraft.domainsText
    );
  }, [draft, initialDraft]);

  const busy = isSubmitting || isValidating;
  const modeLabel = mode === "create" ? "Set up SSO" : "Edit SSO setup";

  const requestClose = () => {
    if (busy) {
      return;
    }
    if (isDirty) {
      setShowDiscardInlineConfirm(true);
      return;
    }
    setShowDiscardInlineConfirm(false);
    onOpenChange(false);
  };

  const handleValidateConnection = async () => {
    setFeedback(null);
    const credentialsErrors = validateCredentials(draft, true);
    if (Object.keys(credentialsErrors).length > 0) {
      setFieldErrors((current) => ({ ...current, ...credentialsErrors }));
      return;
    }

    setFieldErrors((current) => ({
      ...current,
      issuer: undefined,
      clientId: undefined,
      clientSecret: undefined,
    }));

    try {
      const result = await onValidate({
        issuer: normalizeIssuer(draft.issuer),
        clientId: draft.clientId.trim(),
        clientSecret: draft.clientSecret.trim(),
      });
      setValidationResult(result);
      setValidatedSignature(validationSignature);
      setFeedback({
        tone: "success",
        message: "Connection test passed. You can continue.",
      });
    } catch (error) {
      const remediationMessage = hasProblemCode(error, "sso_validation_timeout")
        ? "Validation timed out. Verify network egress from ADE to the issuer and try again."
        : hasProblemCode(error, "sso_issuer_mismatch")
          ? "Issuer mismatch. Confirm the issuer URL exactly matches the metadata issuer."
          : hasProblemCode(error, "sso_metadata_invalid")
            ? "Issuer metadata is missing required endpoints. Verify the issuer and OIDC configuration."
            : hasProblemCode(error, "sso_discovery_failed")
              ? "Could not discover issuer metadata. Verify the issuer URL and credentials, then retry."
              : null;
      const mapped = mapUiError(error, {
        fallback: "Unable to validate provider connection.",
        statusMessages: {
          422: remediationMessage ?? "Provider validation failed. Review issuer metadata and credentials.",
        },
      });
      setFieldErrors((current) => ({
        ...current,
        issuer: findFirstFieldError(mapped.fieldErrors, ["issuer", "body.issuer"]),
        clientId: findFirstFieldError(mapped.fieldErrors, ["clientId", "client_id", "body.clientId", "body.client_id"]),
        clientSecret: findFirstFieldError(mapped.fieldErrors, [
          "clientSecret",
          "client_secret",
          "body.clientSecret",
          "body.client_secret",
        ]),
      }));
      setValidationResult(null);
      setValidatedSignature(null);
      setFeedback({ tone: "danger", message: remediationMessage ?? mapped.message });
    }
  };

  const handleContinue = async () => {
    setFeedback(null);

    if (step === "intro") {
      setStep("basics");
      return;
    }

    if (step === "basics") {
      const basicsErrors = validateBasics(mode, draft);
      setFieldErrors((current) => ({ ...current, ...basicsErrors }));
      if (Object.keys(basicsErrors).length > 0) {
        return;
      }
      setStep("credentials");
      return;
    }

    if (step === "credentials") {
      const credentialsErrors = validateCredentials(
        draft,
        mode === "create",
      );
      setFieldErrors((current) => ({ ...current, ...credentialsErrors }));
      if (Object.keys(credentialsErrors).length > 0) {
        return;
      }
      setStep("test");
      return;
    }

    if (step === "test") {
      if (!validationCurrent) {
        setFeedback({
          tone: "danger",
          message: "Run the connection test and fix any errors before you continue.",
        });
        return;
      }
      setStep("review");
      return;
    }

    if (step === "review") {
      const basicsErrors = validateBasics(mode, draft);
      const credentialsErrors = validateCredentials(
        draft,
        mode === "create" || requiresValidation,
      );
      const nextErrors = { ...basicsErrors, ...credentialsErrors };
      setFieldErrors(nextErrors);
      if (Object.keys(nextErrors).length > 0) {
        setFeedback({
          tone: "danger",
          message: "Review the highlighted fields before saving.",
        });
        return;
      }
      if (!validationCurrent) {
        setStep("test");
        setFeedback({
          tone: "danger",
          message: "Run the connection test and fix any errors before you continue.",
        });
        return;
      }

      try {
        const successMessage =
          mode === "create"
            ? "Provider saved. Review authentication policy before requiring identity provider sign-in."
            : "Provider setup updated.";

        if (mode === "create") {
          await onCreate({
            id: draft.id.trim(),
            type: "oidc",
            label: draft.label.trim(),
            issuer: normalizeIssuer(draft.issuer),
            clientId: draft.clientId.trim(),
            clientSecret: draft.clientSecret.trim(),
            status: draft.status,
            domains: normalizedDomains,
          });
        } else if (provider) {
          await onUpdate(provider.id, {
            label: draft.label.trim(),
            issuer: normalizeIssuer(draft.issuer),
            clientId: draft.clientId.trim(),
            clientSecret: draft.clientSecret.trim() || undefined,
            status: draft.status,
            domains: normalizedDomains,
          });
        }
        onSuccess?.(successMessage);
        setShowDiscardInlineConfirm(false);
        onOpenChange(false);
      } catch (error) {
        const mapped = mapUiError(error, {
          fallback: mode === "create" ? "Unable to save provider setup." : "Unable to update provider setup.",
          statusMessages: {
            409: "Provider ID already exists or provider state changed. Refresh and try again.",
            422: "Provider configuration is invalid. Review details and try again.",
          },
        });
        setFieldErrors((current) => ({
          ...current,
          id: findFirstFieldError(mapped.fieldErrors, ["id", "body.id"]),
          label: findFirstFieldError(mapped.fieldErrors, ["label", "body.label"]),
          issuer: findFirstFieldError(mapped.fieldErrors, ["issuer", "body.issuer"]),
          clientId: findFirstFieldError(mapped.fieldErrors, [
            "clientId",
            "client_id",
            "body.clientId",
            "body.client_id",
          ]),
          clientSecret: findFirstFieldError(mapped.fieldErrors, [
            "clientSecret",
            "client_secret",
            "body.clientSecret",
            "body.client_secret",
          ]),
          domains: findFirstFieldError(mapped.fieldErrors, ["domains", "body.domains"]),
        }));
        setFeedback({ tone: "danger", message: mapped.message });
      }
      return;
    }
  };
  const continueLabel = step === "review" ? "Save provider" : "Continue";
  const continueDisabled =
    busy ||
    !canManage ||
    missingProvider ||
    showDiscardInlineConfirm ||
    (step === "test" && requiresValidation && !validationCurrent);

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => (nextOpen ? onOpenChange(true) : requestClose())}>
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-4xl"
        onCloseAutoFocus={(event) => {
          if (!returnFocusTarget) {
            return;
          }
          event.preventDefault();
          returnFocusTarget.focus();
        }}
      >
          <DialogHeader>
            <DialogTitle>{modeLabel}</DialogTitle>
            <DialogDescription>
              Configure and test your identity provider connection. Policy changes are saved separately.
            </DialogDescription>
          </DialogHeader>

          {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
          {missingProvider ? (
            <Alert tone="danger">Provider could not be loaded. Close this dialog and try again.</Alert>
          ) : null}
          {showDiscardInlineConfirm ? (
            <section className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm">
              <p className="font-semibold text-foreground">Discard setup changes?</p>
              <p className="mt-1 text-muted-foreground">You have unsaved setup changes.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDiscardInlineConfirm(false)}
                >
                  Keep editing
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    setShowDiscardInlineConfirm(false);
                    onOpenChange(false);
                  }}
                >
                  Discard changes
                </Button>
              </div>
            </section>
          ) : null}

          <WizardProgress currentStep={step} />

          {step === "intro" ? (
            <section className="space-y-3 rounded-xl border border-border bg-card p-4">
              <h3 className="text-base font-semibold text-foreground">Prepare your identity provider details</h3>
              <p className="text-sm text-muted-foreground">
                You&apos;ll enter provider metadata, test discovery, then save. Identity provider sign-in requirements are
                controlled separately in Authentication policy.
              </p>
              <div className="rounded-lg border border-border/70 bg-background p-3 text-sm text-muted-foreground">
                <p className="flex items-start gap-2">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  Setup first, policy second: saving provider setup does not turn on identity provider sign-in.
                </p>
              </div>
            </section>
          ) : null}

          {step === "basics" ? (
            <section className="space-y-4 rounded-xl border border-border bg-card p-4">
              <FormField
                label="Provider ID"
                required={mode === "create"}
                hint="Lowercase letters, numbers, dashes, and underscores."
                error={fieldErrors.id}
              >
                <Input
                  value={draft.id}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      id: event.target.value.toLowerCase(),
                    }))
                  }
                  placeholder="okta-primary"
                  disabled={mode === "edit" || busy || !canManage}
                />
              </FormField>

              <FormField label="Label" required error={fieldErrors.label}>
                <Input
                  value={draft.label}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, label: event.target.value }))
                  }
                  placeholder="Okta Workforce"
                  disabled={busy || !canManage}
                />
              </FormField>

              <FormField
                label="Status"
                hint="Active providers can be used for identity provider sign-in."
              >
                <select
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={draft.status}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      status: event.target.value as ProviderStatus,
                    }))
                  }
                  disabled={busy || !canManage}
                >
                  <option value="active">active</option>
                  <option value="disabled">disabled</option>
                </select>
              </FormField>

              <FormField
                label="Allowed domains"
                hint="Comma-separated email domains mapped to this provider."
                error={fieldErrors.domains}
              >
                <Input
                  value={draft.domainsText}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      domainsText: event.target.value,
                    }))
                  }
                  placeholder="example.com, subsidiary.com"
                  disabled={busy || !canManage}
                />
              </FormField>
            </section>
          ) : null}

          {step === "credentials" ? (
            <section className="space-y-4 rounded-xl border border-border bg-card p-4">
              <FormField
                label="Issuer"
                required
                hint="Use the provider issuer URL (must be https)."
                error={fieldErrors.issuer}
              >
                <Input
                  value={draft.issuer}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, issuer: event.target.value }))
                  }
                  placeholder="https://example.okta.com/oauth2/default"
                  disabled={busy || !canManage}
                />
              </FormField>

              <FormField label="Client ID" required error={fieldErrors.clientId}>
                <Input
                  value={draft.clientId}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, clientId: event.target.value }))
                  }
                  disabled={busy || !canManage}
                />
              </FormField>

              <FormField
                label={mode === "create" ? "Client secret" : "Client secret"}
                required={mode === "create" || requiresValidation}
                hint={
                  mode === "edit" && requiresValidation
                    ? "Re-enter client secret to run connection test."
                    : "Stored securely and never shown again."
                }
                error={fieldErrors.clientSecret}
              >
                <Input
                  type="password"
                  value={draft.clientSecret}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, clientSecret: event.target.value }))
                  }
                  disabled={busy || !canManage}
                />
              </FormField>
            </section>
          ) : null}

          {step === "test" ? (
            <section className="space-y-4 rounded-xl border border-border bg-card p-4">
              {requiresValidation ? (
                <>
                  <p className="text-sm text-muted-foreground">
                    Validate issuer metadata before saving this provider.
                  </p>

                  {secretRequiredForValidation ? (
                    <Alert tone="warning" icon={<CircleAlert className="h-4 w-4" />}>
                      Enter client secret to run connection test.
                    </Alert>
                  ) : null}

                  <div className="rounded-lg border border-border/80 bg-background p-3 text-sm text-muted-foreground">
                    <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1">
                      <dt>Issuer</dt>
                      <dd className="break-all">{normalizeIssuer(draft.issuer) || "Not set"}</dd>
                      <dt>Client ID</dt>
                      <dd className="break-all">{draft.clientId.trim() || "Not set"}</dd>
                    </dl>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy || secretRequiredForValidation || !canManage}
                    onClick={() => void handleValidateConnection()}
                  >
                    {isValidating ? "Testing..." : "Test connection"}
                  </Button>

                  {validationCurrent && validationResult ? (
                    <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-foreground">
                      <p className="mb-2 inline-flex items-center gap-2 font-medium">
                        <CheckCircle2 className="h-4 w-4 text-success" />
                        Validation succeeded
                      </p>
                      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        <dt>Issuer</dt>
                        <dd className="break-all">{validationResult.issuer}</dd>
                        <dt>Authorize</dt>
                        <dd className="break-all">{validationResult.authorizationEndpoint}</dd>
                        <dt>Token</dt>
                        <dd className="break-all">{validationResult.tokenEndpoint}</dd>
                        <dt>JWKS</dt>
                        <dd className="break-all">{validationResult.jwksUri}</dd>
                      </dl>
                    </div>
                  ) : null}
                </>
              ) : (
                <Alert tone="info">
                  No connection test is required for this change. Continue to review and save.
                </Alert>
              )}
            </section>
          ) : null}

          {step === "review" ? (
            <section className="space-y-4 rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{mode === "create" ? "New provider" : "Existing provider"}</Badge>
                <Badge variant={draft.status === "active" ? "secondary" : "outline"}>
                  {draft.status}
                </Badge>
                {requiresValidation ? (
                  <Badge variant={validationCurrent ? "secondary" : "outline"}>
                    {validationCurrent ? "Validation passed" : "Validation required"}
                  </Badge>
                ) : null}
              </div>

              <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
                <dt className="text-muted-foreground">Provider ID</dt>
                <dd className="font-mono">{draft.id.trim() || "—"}</dd>
                <dt className="text-muted-foreground">Label</dt>
                <dd>{draft.label.trim() || "—"}</dd>
                <dt className="text-muted-foreground">Issuer</dt>
                <dd className="break-all">{normalizeIssuer(draft.issuer) || "—"}</dd>
                <dt className="text-muted-foreground">Client ID</dt>
                <dd className="break-all">{draft.clientId.trim() || "—"}</dd>
                <dt className="text-muted-foreground">Allowed domains</dt>
                <dd>{normalizedDomains.length > 0 ? normalizedDomains.join(", ") : "No domain restrictions"}</dd>
              </dl>

              <Alert tone="info">
                Saving provider setup does not change authentication policy. Review and save policy changes separately.
              </Alert>
            </section>
          ) : null}

          <div className="flex items-center justify-between gap-2 border-t border-border pt-2">
            <Button
              type="button"
              variant="ghost"
              disabled={busy || showDiscardInlineConfirm || step === "intro"}
              onClick={() => setStep(previousStep(step))}
            >
              Back
            </Button>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={busy || showDiscardInlineConfirm}
                onClick={requestClose}
              >
                Cancel
              </Button>
              <Button
                type="button"
                disabled={continueDisabled}
                onClick={() => void handleContinue()}
              >
                {busy && step === "review"
                  ? "Saving..."
                  : busy && step === "test"
                    ? "Testing..."
                    : continueLabel}
              </Button>
            </div>
          </div>
      </DialogContent>
    </Dialog>
  );
}

function WizardProgress({ currentStep }: { readonly currentStep: WizardStep }) {
  const currentIndex = stepIndex(currentStep);
  return (
    <ol className="grid grid-cols-3 gap-2 text-xs sm:grid-cols-6">
      {STEP_ORDER.map((stepName, index) => {
        const active = index === currentIndex;
        const complete = index < currentIndex;
        return (
          <li
            key={stepName}
            className={cn(
              "rounded-md border px-2 py-1 text-center font-semibold uppercase tracking-wide",
              active && "border-primary bg-primary/10 text-primary",
              complete && "border-success/30 bg-success/10 text-success",
              !active && !complete && "border-border text-muted-foreground",
            )}
          >
            {STEP_LABELS[stepName]}
          </li>
        );
      })}
    </ol>
  );
}
