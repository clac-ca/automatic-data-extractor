import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ShieldCheck, ShieldX } from "lucide-react";

import { mapUiError } from "@/api/uiErrors";
import type { ProblemDetailsErrorMap } from "@/api/errors";
import type { AdminSettingsPatchRequest } from "@/api/admin/settings";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useAdminSettingsQuery, usePatchAdminSettingsMutation } from "@/hooks/admin";
import { Alert } from "@/components/ui/alert";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";
import { SettingsFieldRow } from "../components/SettingsFieldRow";
import { SettingsSaveBar } from "../components/SettingsSaveBar";
import { SettingsTechnicalDetails } from "../components/SettingsTechnicalDetails";
import { findRuntimeSettingFieldError, hasProblemCode } from "../components/runtimeSettingsUtils";

type FeedbackTone = "success" | "danger";
type FeedbackMessage = { tone: FeedbackTone; message: string };

export function SystemSafeModeSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const canManage = hasPermission("system.settings.manage");
  const canRead = hasPermission("system.settings.read") || canManage;

  const settingsQuery = useAdminSettingsQuery({ enabled: canRead });
  const patchSettings = usePatchAdminSettingsMutation();

  const [enabled, setEnabled] = useState(false);
  const [detail, setDetail] = useState("");
  const [feedback, setFeedback] = useState<FeedbackMessage | null>(null);
  const [fieldErrors, setFieldErrors] = useState<ProblemDetailsErrorMap>({});
  const [confirmEnableOpen, setConfirmEnableOpen] = useState(false);
  const [syncedRevision, setSyncedRevision] = useState<number | null>(null);

  const hasUnsavedChanges = useMemo(() => {
    if (!settingsQuery.data) {
      return false;
    }
    const savedDetail = normalizeDetail(settingsQuery.data.values.safeMode.detail || "");
    const draftDetail = normalizeDetail(detail);
    return enabled !== Boolean(settingsQuery.data.values.safeMode.enabled) || draftDetail !== savedDetail;
  }, [detail, enabled, settingsQuery.data]);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    const shouldSyncDraft = syncedRevision === null || (!hasUnsavedChanges && syncedRevision !== settingsQuery.data.revision);
    if (!shouldSyncDraft) {
      return;
    }

    setEnabled(Boolean(settingsQuery.data.values.safeMode.enabled));
    setDetail(settingsQuery.data.values.safeMode.detail || "");
    setSyncedRevision(settingsQuery.data.revision);
    setFieldErrors({});
  }, [hasUnsavedChanges, settingsQuery.data, syncedRevision]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved changes in Run controls. Are you sure you want to leave?",
    shouldBypassNavigation: () => patchSettings.isPending,
  });

  const safeModeMeta = settingsQuery.data?.meta.safeMode;
  const enabledLocked = Boolean(safeModeMeta?.enabled.lockedByEnv);
  const detailLocked = Boolean(safeModeMeta?.detail.lockedByEnv);

  const hasEditableChanges = useMemo(() => {
    if (!settingsQuery.data) {
      return false;
    }
    const savedEnabled = Boolean(settingsQuery.data.values.safeMode.enabled);
    const savedDetail = normalizeDetail(settingsQuery.data.values.safeMode.detail || "");
    const draftDetail = normalizeDetail(detail);

    const enabledChanged = enabled !== savedEnabled && !enabledLocked;
    const detailChanged = draftDetail !== savedDetail && !detailLocked;
    return enabledChanged || detailChanged;
  }, [detail, detailLocked, enabled, enabledLocked, settingsQuery.data]);

  const detailError = findRuntimeSettingFieldError(fieldErrors, "safeMode.detail");
  const enabledError = findRuntimeSettingFieldError(fieldErrors, "safeMode.enabled");

  const resetDraft = () => {
    if (!settingsQuery.data) {
      return;
    }
    setEnabled(Boolean(settingsQuery.data.values.safeMode.enabled));
    setDetail(settingsQuery.data.values.safeMode.detail || "");
    setSyncedRevision(settingsQuery.data.revision);
    setFieldErrors({});
    setFeedback(null);
  };

  const handleSave = async () => {
    setFeedback(null);
    setFieldErrors({});
    const current = settingsQuery.data;
    if (!current) {
      return;
    }

    const safeModeChanges: NonNullable<AdminSettingsPatchRequest["changes"]["safeMode"]> = {};
    if (!enabledLocked && enabled !== Boolean(current.values.safeMode.enabled)) {
      safeModeChanges.enabled = enabled;
    }
    if (!detailLocked && normalizeDetail(detail) !== normalizeDetail(current.values.safeMode.detail || "")) {
      safeModeChanges.detail = detail;
    }
    if (Object.keys(safeModeChanges).length === 0) {
      return;
    }

    try {
      const updated = await patchSettings.mutateAsync({
        revision: current.revision,
        changes: { safeMode: safeModeChanges },
      });
      setSyncedRevision(updated.revision);
      setFeedback({
        tone: "success",
        message: enabled ? "Safe mode enabled." : "Safe mode disabled.",
      });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to update run controls.",
        statusMessages: {
          409: "Settings changed while you were editing. Review your draft and save again.",
        },
      });
      setFeedback({ tone: "danger", message: mapped.message });
      setFieldErrors(mapped.fieldErrors);
      if (hasProblemCode(error, "settings_revision_conflict")) {
        await settingsQuery.refetch();
      }
    }
  };

  if (!canRead) {
    return <Alert tone="danger">You do not have permission to access run controls.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {settingsQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(settingsQuery.error, { fallback: "Unable to load run controls." }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="Run controls"
        description="Pause or resume run creation during incidents or maintenance."
      >
        <Alert
          tone={enabled ? "warning" : "info"}
          heading={enabled ? "Safe mode is active" : "Safe mode is inactive"}
          icon={enabled ? <ShieldX className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
        >
          {enabled
            ? "New runs are blocked until safe mode is disabled."
            : "Run creation is currently allowed."}
        </Alert>

        <div className="space-y-4">
          <SettingsFieldRow
            label="Safe mode enabled"
            description="Immediately block new run creation across ADE."
            meta={safeModeMeta?.enabled}
            error={enabledError}
          >
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={enabled}
                onChange={(event) => {
                  const nextChecked = event.target.checked;
                  if (nextChecked && !enabled) {
                    setConfirmEnableOpen(true);
                    return;
                  }
                  setEnabled(nextChecked);
                }}
                disabled={!canManage || patchSettings.isPending || settingsQuery.isLoading || enabledLocked}
              />
              <span>{enabled ? "Enabled" : "Disabled"}</span>
            </label>
          </SettingsFieldRow>

          <SettingsFieldRow
            label="Safe mode detail message"
            description="Shown to operators and users when safe mode is active."
            hint="Whitespace-only values are normalized to the default detail."
            meta={safeModeMeta?.detail}
            error={detailError}
          >
            <Input
              value={detail}
              onChange={(event) => setDetail(event.target.value)}
              placeholder="Maintenance window"
              disabled={!canManage || patchSettings.isPending || detailLocked}
            />
          </SettingsFieldRow>
        </div>

        {(enabledLocked || detailLocked) ? (
          <Alert tone="info" icon={<AlertTriangle className="h-4 w-4" />}>
            One or more fields are managed by environment variables and cannot be edited here.
          </Alert>
        ) : null}

        <SettingsTechnicalDetails
          settings={settingsQuery.data}
          isLoading={settingsQuery.isLoading}
          onRefresh={() => settingsQuery.refetch()}
        />
      </SettingsSection>

      <SettingsSaveBar
        visible={hasUnsavedChanges}
        canManage={canManage}
        isSaving={patchSettings.isPending}
        canSave={hasEditableChanges}
        onSave={handleSave}
        onDiscard={resetDraft}
      />

      <ConfirmDialog
        open={confirmEnableOpen}
        title="Enable safe mode?"
        description="Enabling safe mode immediately pauses new run execution. Existing runs may continue depending on worker state."
        confirmLabel="Enable safe mode"
        tone="danger"
        onCancel={() => setConfirmEnableOpen(false)}
        onConfirm={() => {
          setEnabled(true);
          setConfirmEnableOpen(false);
        }}
      />
    </div>
  );
}

function normalizeDetail(value: string | null | undefined) {
  return (value ?? "").trim().replace(/\s+/g, " ");
}
