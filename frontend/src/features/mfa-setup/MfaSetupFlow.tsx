import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import QRCode from "qrcode";
import { CheckCircle2, Lock, Smartphone } from "lucide-react";

import {
  confirmMfaEnrollment,
  disableMfa,
  regenerateMfaRecoveryCodes,
  startMfaEnrollment,
  type MfaEnrollStartResponse,
  type MfaStatusResponse,
} from "@/api/auth/api";
import { mapUiError } from "@/api/uiErrors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

interface MfaSetupFlowProps {
  readonly mfaStatus: MfaStatusResponse | null;
  readonly isMfaStatusLoading: boolean;
  readonly mfaStatusError: string | null;
  readonly onRefreshMfaStatus: () => Promise<void>;
  readonly allowSkip?: boolean;
  readonly onboardingRequired?: boolean;
  readonly onSkip?: () => void;
  readonly onFlowComplete?: () => void;
  readonly showStatusCard?: boolean;
  readonly className?: string;
}

type Feedback =
  | { tone: "success"; message: string }
  | { tone: "danger"; message: string }
  | { tone: "info"; message: string }
  | null;

type WizardStep = "welcome" | "apps" | "scan" | "manual" | "verify" | "recovery" | "complete";

type EnrollmentState = Readonly<MfaEnrollStartResponse & { secret: string | null }>;

const AUTH_APP_OPTIONS = [
  {
    name: "Microsoft Authenticator",
    description: "Great choice for Microsoft or enterprise accounts.",
  },
  {
    name: "Google Authenticator",
    description: "Simple and widely used for TOTP codes.",
  },
  {
    name: "Authy",
    description: "Supports multi-device sync and secure backups.",
  },
  {
    name: "Duo Mobile",
    description: "Popular in IT-managed environments.",
  },
] as const;

const PROGRESS_STEPS = ["welcome", "apps", "scan", "verify", "recovery", "complete"] as const;

export function MfaSetupFlow({
  mfaStatus,
  isMfaStatusLoading,
  mfaStatusError,
  onRefreshMfaStatus,
  allowSkip = false,
  onboardingRequired = false,
  onSkip,
  onFlowComplete,
  showStatusCard = true,
  className,
}: MfaSetupFlowProps) {
  const initializedFromStatus = useRef(false);
  const [wizardActive, setWizardActive] = useState(false);
  const [wizardStep, setWizardStep] = useState<WizardStep>("welcome");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [enrollment, setEnrollment] = useState<EnrollmentState | null>(null);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState<string | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [recoveryAcknowledged, setRecoveryAcknowledged] = useState(false);
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false);
  const [disableDialogOpen, setDisableDialogOpen] = useState(false);
  const [regenerationCode, setRegenerationCode] = useState("");

  const [isStartingEnrollment, setIsStartingEnrollment] = useState(false);
  const [isConfirmingEnrollment, setIsConfirmingEnrollment] = useState(false);
  const [isRegeneratingCodes, setIsRegeneratingCodes] = useState(false);
  const [isDisablingMfa, setIsDisablingMfa] = useState(false);

  useEffect(() => {
    if (initializedFromStatus.current || isMfaStatusLoading || !mfaStatus) {
      return;
    }

    initializedFromStatus.current = true;
    setWizardActive(!mfaStatus.enabled);
    setWizardStep(mfaStatus.enabled ? "complete" : "welcome");
  }, [isMfaStatusLoading, mfaStatus]);

  useEffect(() => {
    if (!enrollment?.otpauthUri) {
      setQrCodeDataUrl(null);
      return;
    }

    let cancelled = false;
    void QRCode.toDataURL(enrollment.otpauthUri, {
      width: 320,
      margin: 1,
      errorCorrectionLevel: "M",
      color: {
        dark: "#111827",
        light: "#ffffff",
      },
    })
      .then((dataUrl) => {
        if (!cancelled) {
          setQrCodeDataUrl(dataUrl);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setQrCodeDataUrl(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enrollment]);

  const progressIndex = useMemo(() => {
    const normalizedStep = wizardStep === "manual" ? "scan" : wizardStep;
    const index = PROGRESS_STEPS.indexOf(normalizedStep as (typeof PROGRESS_STEPS)[number]);
    return index >= 0 ? index : 0;
  }, [wizardStep]);

  const handleStartEnrollment = async () => {
    setFeedback(null);
    setIsStartingEnrollment(true);
    try {
      const result = await startMfaEnrollment();
      setEnrollment({ ...result, secret: extractTotpSecret(result.otpauthUri) });
      setVerificationCode("");
      setWizardActive(true);
      setWizardStep("scan");
      setFeedback({ tone: "info", message: "Great. Scan the QR code in your authenticator app." });
    } catch (error) {
      const mapped = mapUiError(error, { fallback: "Unable to start MFA setup." });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsStartingEnrollment(false);
    }
  };

  const handleConfirmEnrollment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = verificationCode.trim();
    if (!code) {
      setFeedback({ tone: "danger", message: "Enter the 6-digit code from your authenticator app." });
      return;
    }

    setFeedback(null);
    setIsConfirmingEnrollment(true);
    try {
      const result = await confirmMfaEnrollment({ code });
      setRecoveryCodes(result.recoveryCodes);
      setRecoveryAcknowledged(false);
      setWizardStep("recovery");
      await onRefreshMfaStatus();
      setFeedback({ tone: "success", message: "MFA enabled. Save your recovery codes before continuing." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to verify your code.",
        statusMessages: {
          400: "That code was not accepted. Wait for a new code and try again.",
        },
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsConfirmingEnrollment(false);
    }
  };

  const handleRegenerateRecoveryCodes = async () => {
    const code = regenerationCode.trim();
    if (!code) {
      setFeedback({ tone: "danger", message: "Enter a valid authenticator or recovery code to continue." });
      return;
    }

    setFeedback(null);
    setIsRegeneratingCodes(true);
    try {
      const result = await regenerateMfaRecoveryCodes({ code });
      setRecoveryCodes(result.recoveryCodes);
      setRecoveryAcknowledged(false);
      setRegenerationCode("");
      setRegenerateDialogOpen(false);
      setWizardActive(true);
      setWizardStep("recovery");
      await onRefreshMfaStatus();
      setFeedback({ tone: "success", message: "Recovery codes regenerated. Save the new set now." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to regenerate recovery codes.",
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsRegeneratingCodes(false);
    }
  };

  const handleDisableMfa = async () => {
    setFeedback(null);
    setIsDisablingMfa(true);
    try {
      await disableMfa();
      await onRefreshMfaStatus();
      setDisableDialogOpen(false);
      setEnrollment(null);
      setVerificationCode("");
      setRecoveryCodes([]);
      setRecoveryAcknowledged(false);
      setWizardActive(true);
      setWizardStep("welcome");
      setFeedback({ tone: "success", message: "MFA was disabled. You can set it up again at any time." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to disable MFA.",
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsDisablingMfa(false);
    }
  };

  const handleCompleteRecoveryStep = async () => {
    setRecoveryCodes([]);
    setRecoveryAcknowledged(false);
    setWizardActive(false);
    setWizardStep("complete");
    await onRefreshMfaStatus();
    setFeedback({ tone: "success", message: "Setup complete. Your account is now protected with MFA." });
    onFlowComplete?.();
  };

  const handleCopy = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setFeedback({ tone: "success", message: `${label} copied to clipboard.` });
    } catch {
      setFeedback({ tone: "danger", message: `Unable to copy ${label.toLowerCase()}. Copy it manually instead.` });
    }
  };

  const handleDownloadRecoveryCodes = () => {
    if (recoveryCodes.length === 0) {
      return;
    }
    const blob = new Blob([`${recoveryCodes.join("\n")}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ade-recovery-codes.txt";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const showWizard =
    wizardActive ||
    wizardStep === "recovery" ||
    (!isMfaStatusLoading && (!mfaStatus || !mfaStatus.enabled));

  return (
    <div className={cn("space-y-5", className)}>
      {mfaStatusError ? <Alert tone="danger">{mfaStatusError}</Alert> : null}
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      {showStatusCard ? (
        <section className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-xs">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={mfaStatus?.enabled ? "secondary" : "outline"}>
              {isMfaStatusLoading ? "Checking status" : mfaStatus?.enabled ? "MFA enabled" : "MFA not enabled"}
            </Badge>
            {mfaStatus?.enrolledAt ? <Badge variant="outline">Enabled on {formatDate(mfaStatus.enrolledAt)}</Badge> : null}
            {mfaStatus?.enabled ? (
              <Badge variant="outline">Recovery codes: {mfaStatus.recoveryCodesRemaining ?? 0}</Badge>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            Use an authenticator app for sign-in verification. You can rotate setup and regenerate recovery codes anytime.
          </p>
        </section>
      ) : null}

      {showWizard ? (
        <section className="space-y-5 rounded-xl border border-border bg-card p-5 shadow-xs">
          <WizardProgress progressIndex={progressIndex} />
          {wizardStep === "welcome" ? (
            <div className="space-y-4 animate-in fade-in-0 slide-in-from-right-2 duration-200">
              <h3 className="text-lg font-semibold text-foreground">Let&apos;s set up MFA</h3>
              <p className="text-sm text-muted-foreground">
                This usually takes about 3 minutes. You&apos;ll install or open an authenticator app, scan a QR code, and
                verify one login code.
              </p>
              <div className="rounded-lg border border-border/80 bg-background p-3 text-sm text-muted-foreground">
                <p className="flex items-start gap-2">
                  <Lock className="mt-0.5 h-4 w-4 shrink-0 text-info" />
                  MFA protects your account if someone gets your password.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => setWizardStep("apps")}>Continue</Button>
                {allowSkip && !onboardingRequired && onSkip ? (
                  <Button type="button" variant="ghost" onClick={onSkip}>
                    Skip for now
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          {wizardStep === "apps" ? (
            <div className="space-y-4 animate-in fade-in-0 slide-in-from-right-2 duration-200">
              <h3 className="text-lg font-semibold text-foreground">Choose an authenticator app</h3>
              <p className="text-sm text-muted-foreground">
                Any TOTP-compatible app works. Here are common options:
              </p>
              <ul className="grid gap-2 sm:grid-cols-2">
                {AUTH_APP_OPTIONS.map((app) => (
                  <li key={app.name} className="rounded-lg border border-border/80 bg-background p-3">
                    <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Smartphone className="h-4 w-4 text-muted-foreground" />
                      {app.name}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">{app.description}</p>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">If you already have an app installed, you can continue now.</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => void handleStartEnrollment()} disabled={isStartingEnrollment}>
                  {isStartingEnrollment ? "Preparing QR code…" : "I have an app"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setWizardStep("welcome")}>
                  Back
                </Button>
                {allowSkip && !onboardingRequired && onSkip ? (
                  <Button type="button" variant="ghost" onClick={onSkip}>
                    Skip for now
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          {wizardStep === "scan" ? (
            <div className="space-y-4 animate-in fade-in-0 slide-in-from-right-2 duration-200">
              <h3 className="text-lg font-semibold text-foreground">Scan this QR code</h3>
              <p className="text-sm text-muted-foreground">
                Open your authenticator app, choose add account, then scan this code.
              </p>
              <div className="mx-auto w-full max-w-xs rounded-xl border border-border bg-background p-4">
                {qrCodeDataUrl ? (
                  <img
                    src={qrCodeDataUrl}
                    alt="QR code for authenticator setup"
                    className="h-auto w-full rounded-md border border-border/70"
                  />
                ) : (
                  <p className="text-center text-sm text-muted-foreground">Generating QR code…</p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => setWizardStep("verify")} disabled={!enrollment}>
                  I scanned it
                </Button>
                <Button type="button" variant="secondary" onClick={() => setWizardStep("manual")} disabled={!enrollment}>
                  Can&apos;t scan? Enter key manually
                </Button>
              </div>
            </div>
          ) : null}

          {wizardStep === "manual" ? (
            <div className="space-y-4 animate-in fade-in-0 slide-in-from-right-2 duration-200">
              <h3 className="text-lg font-semibold text-foreground">Manual setup</h3>
              <p className="text-sm text-muted-foreground">
                In your app, choose manual entry and paste these values.
              </p>
              <FormField label="Setup key" hint={`Issuer: ${enrollment?.issuer ?? "ADE"} · Account: ${enrollment?.accountName ?? ""}`}>
                <div className="flex gap-2">
                  <Input value={enrollment?.secret ?? ""} readOnly className="font-mono" />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleCopy("Setup key", enrollment?.secret ?? "")}
                    disabled={!enrollment?.secret}
                  >
                    Copy
                  </Button>
                </div>
              </FormField>
              <FormField label="Authenticator URI">
                <div className="flex gap-2">
                  <Input value={enrollment?.otpauthUri ?? ""} readOnly className="font-mono text-xs" />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleCopy("Authenticator URI", enrollment?.otpauthUri ?? "")}
                    disabled={!enrollment?.otpauthUri}
                  >
                    Copy
                  </Button>
                </div>
              </FormField>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => setWizardStep("verify")}>Continue</Button>
                <Button type="button" variant="ghost" onClick={() => setWizardStep("scan")}>Back to QR code</Button>
              </div>
            </div>
          ) : null}

          {wizardStep === "verify" ? (
            <form className="space-y-4 animate-in fade-in-0 slide-in-from-right-2 duration-200" onSubmit={handleConfirmEnrollment}>
              <h3 className="text-lg font-semibold text-foreground">Verify your setup</h3>
              <p className="text-sm text-muted-foreground">
                Enter the current 6-digit code from your authenticator app.
              </p>
              <FormField label="One-time code" required hint="Codes refresh every 30 seconds.">
                <Input
                  type="text"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  value={verificationCode}
                  onChange={(event) => setVerificationCode(event.target.value)}
                  disabled={isConfirmingEnrollment}
                />
              </FormField>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={isConfirmingEnrollment}>
                  {isConfirmingEnrollment ? "Verifying…" : "Verify and enable MFA"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setWizardStep("scan")}>
                  Back
                </Button>
              </div>
            </form>
          ) : null}

          {wizardStep === "recovery" ? (
            <div className="space-y-4 animate-in fade-in-0 slide-in-from-right-2 duration-200">
              <h3 className="text-lg font-semibold text-foreground">Save your recovery codes</h3>
              <p className="text-sm text-muted-foreground">
                Store these in a secure location. Each recovery code can be used once if your phone is unavailable.
              </p>
              <ul className="grid gap-2 sm:grid-cols-2">
                {recoveryCodes.map((code) => (
                  <li key={code} className="rounded-md border border-border bg-background px-3 py-2 font-mono text-sm text-foreground">
                    {code}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void handleCopy("Recovery codes", recoveryCodes.join("\n"))}
                  disabled={recoveryCodes.length === 0}
                >
                  Copy all
                </Button>
                <Button type="button" variant="outline" onClick={handleDownloadRecoveryCodes} disabled={recoveryCodes.length === 0}>
                  Download
                </Button>
                <Button type="button" variant="outline" onClick={() => window.print()} disabled={recoveryCodes.length === 0}>
                  Print
                </Button>
              </div>
              <div className="flex items-center gap-2 rounded-md border border-border/80 bg-background px-3 py-2 text-sm text-foreground">
                <Checkbox
                  id="mfa-recovery-ack"
                  checked={recoveryAcknowledged}
                  onCheckedChange={(checked) => setRecoveryAcknowledged(Boolean(checked))}
                />
                <label htmlFor="mfa-recovery-ack" className="cursor-pointer">
                  I saved my recovery codes in a secure place.
                </label>
              </div>
              <Button type="button" disabled={!recoveryAcknowledged} onClick={() => void handleCompleteRecoveryStep()}>
                Continue
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}

      {!showWizard && mfaStatus?.enabled ? (
        <section className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
          <div className="flex flex-wrap items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-success" />
            <h3 className="text-base font-semibold text-foreground">MFA is active</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            Your account is protected with TOTP verification. Keep your recovery posture current.
          </p>
          <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
            <p className="rounded-md border border-border/80 bg-background px-3 py-2">
              Recovery codes remaining: <span className="font-semibold text-foreground">{mfaStatus?.recoveryCodesRemaining ?? 0}</span>
            </p>
            <p className="rounded-md border border-border/80 bg-background px-3 py-2">
              Enrolled: <span className="font-semibold text-foreground">{mfaStatus?.enrolledAt ? formatDate(mfaStatus.enrolledAt) : "Unknown"}</span>
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setRegenerationCode("");
                setRegenerateDialogOpen(true);
              }}
            >
              Regenerate recovery codes
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setWizardActive(true);
                setWizardStep("apps");
              }}
            >
              Set up again
            </Button>
            <Button type="button" variant="destructive" onClick={() => setDisableDialogOpen(true)}>
              Disable MFA
            </Button>
          </div>
          <Alert tone="info">
            If you lose your device, use a saved recovery code to sign in, then regenerate new recovery codes.
          </Alert>
        </section>
      ) : null}

      <ConfirmDialog
        open={regenerateDialogOpen}
        title="Regenerate recovery codes"
        description="Enter a current authenticator code or recovery code to confirm."
        confirmLabel={isRegeneratingCodes ? "Regenerating…" : "Regenerate"}
        cancelLabel="Cancel"
        confirmDisabled={regenerationCode.trim().length === 0}
        isConfirming={isRegeneratingCodes}
        onCancel={() => {
          if (isRegeneratingCodes) {
            return;
          }
          setRegenerateDialogOpen(false);
        }}
        onConfirm={() => {
          void handleRegenerateRecoveryCodes();
        }}
      >
        <FormField label="Verification code" required hint="Accepts 6-digit authenticator code or 8-character recovery code.">
          <Input
            value={regenerationCode}
            onChange={(event) => setRegenerationCode(event.target.value)}
            autoComplete="one-time-code"
            placeholder="123456"
            disabled={isRegeneratingCodes}
          />
        </FormField>
      </ConfirmDialog>

      <ConfirmDialog
        open={disableDialogOpen}
        title="Disable MFA?"
        description="This removes extra sign-in protection until you enable MFA again."
        confirmLabel={isDisablingMfa ? "Disabling…" : "Disable MFA"}
        cancelLabel="Cancel"
        tone="danger"
        isConfirming={isDisablingMfa}
        onCancel={() => {
          if (isDisablingMfa) {
            return;
          }
          setDisableDialogOpen(false);
        }}
        onConfirm={() => {
          void handleDisableMfa();
        }}
      >
        {mfaStatus?.enabled ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-foreground">
            You may be blocked from disabling MFA when SSO enforcement is active for global-admin accounts.
          </p>
        ) : (
          <p className="rounded-md border border-border/80 bg-background px-3 py-2 text-sm text-muted-foreground">
            MFA is already disabled.
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}

function WizardProgress({ progressIndex }: { readonly progressIndex: number }) {
  return (
    <ol className="grid gap-2 text-xs sm:grid-cols-6" aria-label="MFA setup progress">
      {PROGRESS_STEPS.map((step, index) => {
        const isComplete = index < progressIndex;
        const isCurrent = index === progressIndex;
        return (
          <li
            key={step}
            className={`rounded-md border px-2 py-1.5 text-center font-medium uppercase tracking-wide ${
              isComplete
                ? "border-success/40 bg-success/15 text-success"
                : isCurrent
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-background text-muted-foreground"
            }`}
          >
            {step}
          </li>
        );
      })}
    </ol>
  );
}

function extractTotpSecret(otpauthUri: string): string | null {
  try {
    const uri = new URL(otpauthUri);
    const secret = uri.searchParams.get("secret")?.trim() ?? "";
    return secret.length > 0 ? secret : null;
  } catch {
    return null;
  }
}
