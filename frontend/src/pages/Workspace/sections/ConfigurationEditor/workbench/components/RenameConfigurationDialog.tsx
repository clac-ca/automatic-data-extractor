import { useEffect, useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";

interface RenameConfigurationDialogProps {
  readonly open: boolean;
  readonly currentName: string;
  readonly error?: string | null;
  readonly isSubmitting?: boolean;
  readonly onCancel: () => void;
  readonly onConfirm: (nextName: string) => void;
}

const MAX_CONFIGURATION_NAME_LENGTH = 255;

export function RenameConfigurationDialog({
  open,
  currentName,
  error,
  isSubmitting = false,
  onCancel,
  onConfirm,
}: RenameConfigurationDialogProps) {
  const [nextName, setNextName] = useState(currentName);
  const [dismissServerError, setDismissServerError] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    setNextName(currentName);
    setDismissServerError(false);
  }, [currentName, open]);

  const trimmedCurrent = currentName.trim();
  const trimmedNext = nextName.trim();
  const hasChanged = trimmedNext.length > 0 && trimmedNext !== trimmedCurrent;

  const validationError = useMemo(() => {
    if (trimmedNext.length === 0) {
      return "Configuration name is required.";
    }
    if (trimmedNext.length > MAX_CONFIGURATION_NAME_LENGTH) {
      return `Configuration name must be ${MAX_CONFIGURATION_NAME_LENGTH} characters or less.`;
    }
    if (!hasChanged) {
      return "Enter a new name to rename this draft.";
    }
    return null;
  }, [hasChanged, trimmedNext]);

  const inlineError = validationError ?? (dismissServerError ? null : error ?? null);

  return (
    <ConfirmDialog
      open={open}
      title="Rename configuration"
      description="Draft-only action. Choose a clear name for this configuration."
      confirmLabel="Save name"
      cancelLabel="Cancel"
      onCancel={onCancel}
      onConfirm={() => onConfirm(trimmedNext)}
      isConfirming={isSubmitting}
      confirmDisabled={Boolean(inlineError) || isSubmitting}
    >
      <FormField label="Configuration name" required>
        <Input
          value={nextName}
          maxLength={MAX_CONFIGURATION_NAME_LENGTH}
          autoFocus
          onChange={(event) => {
            setNextName(event.target.value);
            if (!dismissServerError) {
              setDismissServerError(true);
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !inlineError && !isSubmitting) {
              event.preventDefault();
              onConfirm(trimmedNext);
            }
          }}
          placeholder="My configuration"
          disabled={isSubmitting}
        />
      </FormField>
      {inlineError ? <p className="text-sm font-medium text-destructive">{inlineError}</p> : null}
    </ConfirmDialog>
  );
}
