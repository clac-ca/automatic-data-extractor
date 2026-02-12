import { useEffect, useMemo, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useUnsavedChangesGuard } from "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard";

import { normalizeSettingsError, useOrganizationRuntimeSettingsQuery, usePatchOrganizationRuntimeSettingsMutation } from "../../data";
import { settingsPaths } from "../../routing/contracts";
import { SettingsAccessDenied, SettingsDetailLayout, SettingsDetailSection, SettingsErrorState, SettingsStickyActionBar } from "../../shared";

function normalizeDetail(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

const RUN_CONTROL_SECTIONS = [{ id: "safe-mode", label: "Safe mode" }] as const;

export function OrganizationRunControlsPage() {
  const { permissions } = useGlobalPermissions();
  const canManage = permissions.has("system.settings.manage");
  const canRead = permissions.has("system.settings.read") || canManage;

  const settingsQuery = useOrganizationRuntimeSettingsQuery(canRead);
  const patchMutation = usePatchOrganizationRuntimeSettingsMutation();

  const [enabled, setEnabled] = useState(false);
  const [detail, setDetail] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [confirmEnableOpen, setConfirmEnableOpen] = useState(false);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    setEnabled(settingsQuery.data.values.safeMode.enabled);
    setDetail(settingsQuery.data.values.safeMode.detail || "");
  }, [settingsQuery.data]);

  const hasUnsavedChanges = useMemo(() => {
    if (!settingsQuery.data) {
      return false;
    }
    const safeMode = settingsQuery.data.values.safeMode;
    return enabled !== safeMode.enabled || normalizeDetail(detail) !== normalizeDetail(safeMode.detail || "");
  }, [detail, enabled, settingsQuery.data]);

  useUnsavedChangesGuard({
    isDirty: hasUnsavedChanges,
    message: "You have unsaved run control changes.",
    shouldBypassNavigation: () => patchMutation.isPending,
  });

  if (!canRead) {
    return <SettingsAccessDenied returnHref={settingsPaths.home} />;
  }

  if (settingsQuery.isError || !settingsQuery.data) {
    return (
      <SettingsErrorState
        title="Run controls unavailable"
        message={normalizeSettingsError(settingsQuery.error, "Unable to load run controls.").message}
      />
    );
  }

  const settings = settingsQuery.data;

  return (
    <SettingsDetailLayout
      title="Run controls"
      subtitle="Control safe mode behavior for run creation during incidents or maintenance windows."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "Run controls" },
      ]}
      actions={
        <Button
          variant={enabled ? "destructive" : "secondary"}
          disabled={!canManage || patchMutation.isPending}
          onClick={() => {
            if (!enabled) {
              setConfirmEnableOpen(true);
              return;
            }
            setEnabled(false);
          }}
        >
          {enabled ? "Disable safe mode" : "Enable safe mode"}
        </Button>
      }
      sections={RUN_CONTROL_SECTIONS}
      defaultSectionId="safe-mode"
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      <SettingsDetailSection id="safe-mode" title="Safe mode">
        <Alert tone={enabled ? "warning" : "info"}>
          {enabled
            ? "Safe mode is active. New runs are blocked until you disable it."
            : "Safe mode is inactive. Run creation is allowed."}
        </Alert>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => {
              const nextChecked = event.target.checked;
              if (nextChecked && !enabled) {
                setConfirmEnableOpen(true);
                return;
              }
              setEnabled(nextChecked);
            }}
            disabled={!canManage || patchMutation.isPending}
          />
          Safe mode enabled
        </label>

        <FormField label="Safe mode detail message" hint="Displayed while safe mode is active.">
          <Input
            value={detail}
            onChange={(event) => setDetail(event.target.value)}
            disabled={!canManage || patchMutation.isPending}
            placeholder="Maintenance window in progress"
          />
        </FormField>
      </SettingsDetailSection>

      <SettingsStickyActionBar
        visible={hasUnsavedChanges}
        canSave={canManage}
        isSaving={patchMutation.isPending}
        onSave={() => {
          setErrorMessage(null);
          setSuccessMessage(null);
          void patchMutation
            .mutateAsync({
              revision: settings.revision,
              changes: {
                safeMode: {
                  enabled,
                  detail,
                },
              },
            })
            .then(() => {
              setSuccessMessage(enabled ? "Safe mode enabled." : "Safe mode disabled.");
            })
            .catch((error) => {
              setErrorMessage(normalizeSettingsError(error, "Unable to update run controls.").message);
            });
        }}
        onDiscard={() => {
          setEnabled(settings.values.safeMode.enabled);
          setDetail(settings.values.safeMode.detail || "");
          setErrorMessage(null);
          setSuccessMessage(null);
        }}
        message="Run control changes are pending"
      />

      <ConfirmDialog
        open={confirmEnableOpen}
        title="Enable safe mode?"
        description="Enabling safe mode immediately blocks new run creation."
        confirmLabel="Enable safe mode"
        tone="danger"
        onCancel={() => setConfirmEnableOpen(false)}
        onConfirm={() => {
          setEnabled(true);
          setConfirmEnableOpen(false);
        }}
      />
    </SettingsDetailLayout>
  );
}
