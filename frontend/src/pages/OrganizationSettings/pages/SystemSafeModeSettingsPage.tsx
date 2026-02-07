import { useEffect, useMemo, useState } from "react";

import { mapUiError } from "@/api/uiErrors";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useSafeModeQuery, useUpdateSafeModeMutation } from "@/hooks/admin";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";

type FeedbackTone = "success" | "danger";
type FeedbackMessage = { tone: FeedbackTone; message: string };

export function SystemSafeModeSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const canManage = hasPermission("system.settings.manage");
  const canRead = hasPermission("system.settings.read") || canManage;

  const safeModeQuery = useSafeModeQuery({ enabled: canRead });
  const updateSafeMode = useUpdateSafeModeMutation();

  const [enabled, setEnabled] = useState(false);
  const [detail, setDetail] = useState("");
  const [feedback, setFeedback] = useState<FeedbackMessage | null>(null);
  const [confirmEnableOpen, setConfirmEnableOpen] = useState(false);

  useEffect(() => {
    if (!safeModeQuery.data) {
      return;
    }
    setEnabled(Boolean(safeModeQuery.data.enabled));
    setDetail(safeModeQuery.data.detail || "");
  }, [safeModeQuery.data]);

  const hasUnsavedChanges = useMemo(() => {
    if (!safeModeQuery.data) {
      return false;
    }
    const savedDetail = normalizeDetail(safeModeQuery.data.detail || "");
    const draftDetail = normalizeDetail(detail);
    return enabled !== Boolean(safeModeQuery.data.enabled) || draftDetail !== savedDetail;
  }, [detail, enabled, safeModeQuery.data]);

  if (!canRead) {
    return <Alert tone="danger">You do not have permission to access safe mode settings.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {safeModeQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(safeModeQuery.error, { fallback: "Unable to load safe mode settings." }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="Safe mode"
        description="Pause engine execution during incidents or maintenance windows."
        actions={
          <Button
            type="button"
            disabled={!canManage || updateSafeMode.isPending || !hasUnsavedChanges}
            onClick={async () => {
              setFeedback(null);
              try {
                await updateSafeMode.mutateAsync({ enabled, detail: detail.trim() || null });
                setFeedback({
                  tone: "success",
                  message: enabled ? "Safe mode enabled." : "Safe mode disabled.",
                });
              } catch (error) {
                const mapped = mapUiError(error, {
                  fallback: "Unable to update safe mode settings.",
                });
                setFeedback({ tone: "danger", message: mapped.message });
              }
            }}
          >
            {updateSafeMode.isPending ? "Saving..." : "Save"}
          </Button>
        }
      >
        <div className="rounded-lg border border-warning/30 bg-warning/10 p-4">
          <p className="text-sm font-semibold text-warning-foreground">Operational impact</p>
          <p className="mt-1 text-xs text-warning-foreground/90">
            When safe mode is enabled, new engine runs are blocked. Keep the detail message clear so operators and
            tenants understand why automation is paused.
          </p>
        </div>

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
            disabled={!canManage || updateSafeMode.isPending || safeModeQuery.isLoading}
          />
          Enable safe mode
        </label>

        <FormField label="Detail" hint="Optional operator-facing message for safe mode state.">
          <Input
            value={detail}
            onChange={(event) => setDetail(event.target.value)}
            placeholder="Maintenance window"
            disabled={!canManage || updateSafeMode.isPending}
          />
        </FormField>

        {hasUnsavedChanges ? (
          <p className="text-xs font-medium text-warning">You have unsaved safe mode changes.</p>
        ) : null}
      </SettingsSection>

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
