import { useEffect, useMemo, useState } from "react";

import { useSession } from "@shared/auth/context/SessionContext";
import {
  DEFAULT_SAFE_MODE_MESSAGE,
  useSafeModeStatus,
  useUpdateSafeModeStatus,
} from "@shared/system";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { TextArea } from "@ui/Input";

export function SafeModeControls() {
  const session = useSession();
  const safeModeStatus = useSafeModeStatus();
  const updateSafeMode = useUpdateSafeModeStatus();
  const [detail, setDetail] = useState(DEFAULT_SAFE_MODE_MESSAGE);

  const currentStatus = safeModeStatus.data;
  useEffect(() => {
    if (currentStatus?.detail) {
      setDetail(currentStatus.detail);
    }
  }, [currentStatus?.detail]);

  const canManageSafeMode = useMemo(() => {
    const permissions = (session.user.permissions ?? []).map((key) => key.toLowerCase());
    return permissions.includes("system.settings.manage");
  }, [session.user.permissions]);

  const isPending = safeModeStatus.isFetching || updateSafeMode.isPending;
  const normalizedDetail = detail.trim() || DEFAULT_SAFE_MODE_MESSAGE;

  const handleToggle = (enabled: boolean) => {
    updateSafeMode.mutate(
      { enabled, detail: normalizedDetail },
      {
        onSuccess: (nextStatus) => {
          setDetail(nextStatus.detail);
        },
      },
    );
  };

  return (
    <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-900">ADE safe mode</h2>
        <p className="text-sm text-slate-500">
          Toggle whether streamed runs should short-circuit before invoking the ADE engine. Use this to pause execution during
          maintenance or while verifying a new config release.
        </p>
      </header>

      {safeModeStatus.isError ? (
        <Alert tone="danger">Unable to load safe mode status.</Alert>
      ) : null}

      {!canManageSafeMode ? (
        <Alert tone="warning">
          You need the <strong>system.settings.manage</strong> permission to change safe mode.
        </Alert>
      ) : null}

      <div className="flex items-center gap-3 text-sm">
        <span
          className={
            currentStatus?.enabled
              ? "inline-flex rounded-full bg-amber-100 px-3 py-1 font-semibold text-amber-800"
              : "inline-flex rounded-full bg-emerald-100 px-3 py-1 font-semibold text-emerald-800"
          }
        >
          {currentStatus?.enabled ? "Safe mode enabled" : "Safe mode disabled"}
        </span>
        <span className="text-slate-500">
          {safeModeStatus.isFetching
            ? "Checking safe mode state..."
            : currentStatus?.detail ?? DEFAULT_SAFE_MODE_MESSAGE}
        </span>
      </div>

      <FormField
        label="Safe mode message"
        hint="Shown in the health check and workspace banner when safe mode is active."
      >
        <TextArea
          value={detail}
          onChange={(event) => setDetail(event.target.value)}
          disabled={!canManageSafeMode || isPending}
        />
      </FormField>

      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={() => setDetail(currentStatus?.detail ?? DEFAULT_SAFE_MODE_MESSAGE)}
          disabled={!canManageSafeMode || isPending}
        >
          Reset message
        </Button>
        <Button
          type="button"
          variant={currentStatus?.enabled ? "primary" : "danger"}
          onClick={() => handleToggle(!currentStatus?.enabled)}
          isLoading={updateSafeMode.isPending}
          disabled={!canManageSafeMode}
        >
          {currentStatus?.enabled ? "Disable safe mode" : "Enable safe mode"}
        </Button>
      </div>
    </div>
  );
}

SafeModeControls.displayName = "SafeModeControls";
