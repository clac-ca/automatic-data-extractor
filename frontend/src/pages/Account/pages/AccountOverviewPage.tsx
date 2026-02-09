import { Link } from "react-router-dom";
import { ShieldCheck, ShieldAlert, KeyRound, UserRound } from "lucide-react";

import type { MfaStatusResponse } from "@/api/auth/api";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface AccountOverviewPageProps {
  readonly mfaStatus: MfaStatusResponse | null;
  readonly isMfaStatusLoading: boolean;
  readonly mfaStatusError: string | null;
  readonly canManageApiKeys: boolean;
}

export function AccountOverviewPage({
  mfaStatus,
  isMfaStatusLoading,
  mfaStatusError,
  canManageApiKeys,
}: AccountOverviewPageProps) {
  const statusLabel = isMfaStatusLoading
    ? "Checking"
    : mfaStatus?.enabled
      ? "Enabled"
      : "Not enabled";
  const recoveryLabel = isMfaStatusLoading
    ? "Checking recovery posture"
    : mfaStatus?.enabled
      ? `Recovery codes remaining: ${mfaStatus.recoveryCodesRemaining ?? 0}`
      : "Recovery codes will be generated during setup";

  return (
    <div className="space-y-6">
      {mfaStatusError ? <Alert tone="danger">{mfaStatusError}</Alert> : null}

      <section className="grid gap-4 md:grid-cols-2">
        <article className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
          <header className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Security health</p>
            <h3 className="text-lg font-semibold text-foreground">Account protection</h3>
          </header>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={mfaStatus?.enabled ? "secondary" : "outline"}>{statusLabel}</Badge>
            {mfaStatus?.enabled ? (
              <Badge variant="secondary">Recovery configured</Badge>
            ) : (
              <Badge variant="outline">Recovery pending</Badge>
            )}
          </div>

          <p className="text-sm text-muted-foreground">{recoveryLabel}</p>

          <div className="rounded-lg border border-border/80 bg-background p-3 text-sm text-muted-foreground">
            {mfaStatus?.enabled ? (
              <p className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                Your account is protected with TOTP MFA. Keep recovery codes in a safe location.
              </p>
            ) : (
              <p className="flex items-start gap-2">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                MFA is not enabled yet. Setup takes about 3 minutes and makes sign-in much safer.
              </p>
            )}
          </div>
        </article>

        <article className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
          <header className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Quick actions</p>
            <h3 className="text-lg font-semibold text-foreground">Jump to common tasks</h3>
          </header>
          <div className="grid gap-2">
            <Button asChild variant="outline" className="justify-start">
              <Link to="/account/security">
                <ShieldCheck className="h-4 w-4" />
                {mfaStatus?.enabled ? "Manage MFA" : "Set up MFA"}
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-start">
              <Link to="/account/profile">
                <UserRound className="h-4 w-4" />
                Edit profile
              </Link>
            </Button>
            {canManageApiKeys ? (
              <Button asChild variant="outline" className="justify-start">
                <Link to="/account/api-keys">
                  <KeyRound className="h-4 w-4" />
                  Manage API keys
                </Link>
              </Button>
            ) : null}
          </div>
        </article>
      </section>

      <article className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-xs">
        <header>
          <h3 className="text-base font-semibold text-foreground">Need help?</h3>
          <p className="text-sm text-muted-foreground">Common questions for getting your account secured.</p>
        </header>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="rounded-md border border-border/80 bg-background px-3 py-2">
            What app should I use? Microsoft Authenticator, Google Authenticator, Authy, and Duo Mobile all work.
          </li>
          <li className="rounded-md border border-border/80 bg-background px-3 py-2">
            Can&apos;t scan the QR code? Use the manual setup key shown during MFA setup.
          </li>
          <li className="rounded-md border border-border/80 bg-background px-3 py-2">
            Lost your phone? Use a saved recovery code to sign in, then regenerate a new set.
          </li>
        </ul>
      </article>
    </div>
  );
}
