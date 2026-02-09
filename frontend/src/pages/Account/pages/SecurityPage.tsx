import { useMemo, useState, type FormEvent } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useLocation } from "react-router-dom";

import { changePassword, type MfaStatusResponse } from "@/api/auth/api";
import { mapUiError } from "@/api/uiErrors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MfaSetupFlow } from "@/features/mfa-setup";

interface SecurityPageProps {
  readonly mfaStatus: MfaStatusResponse | null;
  readonly isMfaStatusLoading: boolean;
  readonly mfaStatusError: string | null;
  readonly onRefreshMfaStatus: () => Promise<void>;
}

export function SecurityPage({
  mfaStatus,
  isMfaStatusLoading,
  mfaStatusError,
  onRefreshMfaStatus,
}: SecurityPageProps) {
  const location = useLocation();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [isPasswordSubmitting, setIsPasswordSubmitting] = useState(false);
  const passwordChangeRequired = useMemo(
    () => new URLSearchParams(location.search).get("requirePasswordChange") === "1",
    [location.search],
  );
  const statusLabel = isMfaStatusLoading
    ? "Checking"
    : mfaStatus?.enabled
      ? "MFA enabled"
      : "MFA not enabled";

  const handlePasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!currentPassword.trim()) {
      setPasswordError("Enter your current password.");
      return;
    }
    if (!newPassword.trim()) {
      setPasswordError("Enter a new password.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }

    setIsPasswordSubmitting(true);
    try {
      await changePassword({
        currentPassword,
        newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess("Password updated.");
    } catch (error) {
      const mapped = mapUiError(error, { fallback: "Unable to change password." });
      setPasswordError(mapped.message);
    } finally {
      setIsPasswordSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      {mfaStatusError ? <Alert tone="danger">{mfaStatusError}</Alert> : null}
      {passwordChangeRequired ? (
        <Alert tone="warning">
          You must change your password before using other areas of the application.
        </Alert>
      ) : null}

      <section className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={mfaStatus?.enabled ? "secondary" : "outline"}>{statusLabel}</Badge>
          {!isMfaStatusLoading ? (
            <Badge variant="outline">
              {mfaStatus?.enabled
                ? `Recovery codes: ${mfaStatus.recoveryCodesRemaining ?? 0}`
                : "Recovery pending"}
            </Badge>
          ) : null}
        </div>

        <p className="text-sm text-muted-foreground">
          {mfaStatus?.enabled
            ? "Your account is protected with TOTP MFA. You can rotate setup and regenerate recovery codes."
            : "Set up MFA to reduce account takeover risk. The guided flow takes about 3 minutes."}
        </p>

        <div className="rounded-lg border border-border/80 bg-background p-3 text-sm text-muted-foreground">
          {mfaStatus?.enabled ? (
            <p className="flex items-start gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
              MFA is active for your sign-ins.
            </p>
          ) : (
            <p className="flex items-start gap-2">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              MFA is not active yet. Use the guided setup to enable it.
            </p>
          )}
        </div>

        <Button type="button" onClick={() => setDialogOpen(true)}>
          {mfaStatus?.enabled ? "Manage MFA" : "Set up MFA"}
        </Button>
      </section>

      <section className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-foreground">Password</h3>
          <p className="text-sm text-muted-foreground">
            Change your password for password sign-in sessions.
          </p>
        </div>

        {passwordError ? <Alert tone="danger">{passwordError}</Alert> : null}
        {passwordSuccess ? <Alert tone="success">{passwordSuccess}</Alert> : null}

        <form className="space-y-4" onSubmit={handlePasswordSubmit}>
          <FormField label="Current password" required>
            <Input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              disabled={isPasswordSubmitting}
            />
          </FormField>
          <FormField label="New password" required>
            <Input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              disabled={isPasswordSubmitting}
            />
          </FormField>
          <FormField label="Confirm new password" required>
            <Input
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              disabled={isPasswordSubmitting}
            />
          </FormField>
          <div className="flex justify-end">
            <Button type="submit" disabled={isPasswordSubmitting}>
              {isPasswordSubmitting ? "Saving..." : "Change password"}
            </Button>
          </div>
        </form>
      </section>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl" showCloseButton>
          <DialogHeader>
            <DialogTitle>{mfaStatus?.enabled ? "Manage MFA" : "Set up MFA"}</DialogTitle>
            <DialogDescription>
              Follow the guided flow to enroll an authenticator app, verify your code, and save recovery codes.
            </DialogDescription>
          </DialogHeader>
          <MfaSetupFlow
            mfaStatus={mfaStatus}
            isMfaStatusLoading={isMfaStatusLoading}
            mfaStatusError={mfaStatusError}
            onRefreshMfaStatus={onRefreshMfaStatus}
            showStatusCard={false}
            onFlowComplete={() => {
              setDialogOpen(false);
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
