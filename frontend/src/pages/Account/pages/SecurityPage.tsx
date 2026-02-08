import { useState } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";

import type { MfaStatusResponse } from "@/api/auth/api";
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
  const [dialogOpen, setDialogOpen] = useState(false);
  const statusLabel = isMfaStatusLoading
    ? "Checking"
    : mfaStatus?.enabled
      ? "MFA enabled"
      : "MFA not enabled";

  return (
    <div className="space-y-5">
      {mfaStatusError ? <Alert tone="danger">{mfaStatusError}</Alert> : null}

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
