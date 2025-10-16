import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";

import type {
  ConfigurationColumn,
  ConfigurationColumnInput,
  ConfigurationScriptVersion,
} from "../../../shared/types/configurations";
import { Alert, Button, FormField, Input, Select, TextArea } from "../../../ui";
import { useConfigurationColumnsQuery } from "../hooks/useConfigurationColumnsQuery";
import { useReplaceConfigurationColumnsMutation } from "../hooks/useReplaceConfigurationColumnsMutation";
import { useScriptVersionsQuery } from "../hooks/useScriptVersionsQuery";

export interface ConfigurationColumnsEditorProps {
  readonly workspaceId: string;
  readonly configurationId: string | null;
  readonly onManageScript: (canonicalKey: string) => void;
}

interface ColumnDraft {
  readonly id: string;
  canonicalKey: string;
  displayLabel: string;
  headerColor: string;
  width: string;
  required: boolean;
  enabled: boolean;
  scriptVersionId: string | null;
  paramsText: string;
}

interface ColumnDraftError {
  canonicalKey?: string;
  displayLabel?: string;
  width?: string;
  paramsText?: string;
}

export function ConfigurationColumnsEditor({
  workspaceId,
  configurationId,
  onManageScript,
}: ConfigurationColumnsEditorProps) {
  const { data: columns, isLoading, isError, refetch } = useConfigurationColumnsQuery(
    workspaceId,
    configurationId ?? "",
  );
  const [drafts, setDrafts] = useState<ColumnDraft[]>([]);
  const [errors, setErrors] = useState<Record<string, ColumnDraftError>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  const replaceMutation = useReplaceConfigurationColumnsMutation(
    workspaceId,
    configurationId ?? "",
  );

  useEffect(() => {
    if (!columns) {
      setDrafts([]);
      return;
    }
    setDrafts(
      columns.map((column) => ({
        id: buildDraftId(column),
        canonicalKey: column.canonical_key,
        displayLabel: column.display_label,
        headerColor: column.header_color ?? "",
        width: column.width != null ? String(column.width) : "",
        required: column.required,
        enabled: column.enabled,
        scriptVersionId: column.script_version_id ?? null,
        paramsText: formatParams(column.params),
      })),
    );
    setErrors({});
    setIsDirty(false);
  }, [columns]);

  const columnCount = drafts.length;

  const handleChange = (id: string, updater: (draft: ColumnDraft) => ColumnDraft) => {
    setDrafts((current) => current.map((draft) => (draft.id === id ? updater(draft) : draft)));
    setIsDirty(true);
    setSuccessMessage(null);
  };

  const handleInputChange = (
    id: string,
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
    const { name, value } = target;
    if (target instanceof HTMLInputElement && target.type === "checkbox") {
      const checked = target.checked;
      handleChange(id, (draft) => ({ ...draft, [name]: checked }));
      return;
    }
    handleChange(id, (draft) => ({ ...draft, [name]: value }));
  };

  const handleSelectScript = (id: string, scriptVersionId: string | null) => {
    handleChange(id, (draft) => ({ ...draft, scriptVersionId }));
  };

  const handleMove = (id: string, direction: -1 | 1) => {
    setDrafts((current) => {
      const index = current.findIndex((draft) => draft.id === id);
      if (index === -1) {
        return current;
      }
      const targetIndex = index + direction;
      if (targetIndex < 0 || targetIndex >= current.length) {
        return current;
      }
      const copy = [...current];
      const [moved] = copy.splice(index, 1);
      copy.splice(targetIndex, 0, moved);
      return copy;
    });
    setIsDirty(true);
  };

  const handleRemove = (id: string) => {
    const draft = drafts.find((item) => item.id === id);
    if (draft && draft.scriptVersionId) {
      const confirmed = window.confirm(
        `Remove column "${draft.displayLabel || draft.canonicalKey}"? Bound scripts will be detached.`,
      );
      if (!confirmed) {
        return;
      }
    }
    setDrafts((current) => current.filter((draft) => draft.id !== id));
    setIsDirty(true);
  };

  const handleAddColumn = () => {
    setDrafts((current) => [
      ...current,
      {
        id: createDraftId(),
        canonicalKey: "",
        displayLabel: "",
        headerColor: "",
        width: "",
        required: false,
        enabled: true,
        scriptVersionId: null,
        paramsText: "{}",
      },
    ]);
    setIsDirty(true);
    setSuccessMessage(null);
  };

  const validation = useMemo(() => validateDrafts(drafts), [drafts]);

  useEffect(() => {
    setErrors(validation.fieldErrors);
  }, [validation.fieldErrors]);

  const handleSave = async () => {
    if (!configurationId) {
      return;
    }

    if (validation.hasErrors) {
      setSuccessMessage(null);
      return;
    }

    const payload: ConfigurationColumnInput[] = drafts.map((draft, index) => ({
      canonical_key: draft.canonicalKey.trim(),
      ordinal: index,
      display_label: draft.displayLabel.trim(),
      header_color: draft.headerColor.trim() || null,
      width: draft.width ? Number(draft.width) : null,
      required: draft.required,
      enabled: draft.enabled,
      script_version_id: draft.scriptVersionId ?? undefined,
      params: validation.paramsById[draft.id] ?? {},
    }));

    try {
      const response = await replaceMutation.mutateAsync(payload);
      setDrafts(
        response.map((column) => ({
          id: buildDraftId(column),
          canonicalKey: column.canonical_key,
          displayLabel: column.display_label,
          headerColor: column.header_color ?? "",
          width: column.width != null ? String(column.width) : "",
          required: column.required,
          enabled: column.enabled,
          scriptVersionId: column.script_version_id ?? null,
          paramsText: formatParams(column.params),
        })),
      );
      setIsDirty(false);
      setSuccessMessage("Columns saved successfully.");
      setErrors({});
    } catch (error) {
      console.error("Failed to save configuration columns", error);
    }
  };

  if (!configurationId) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
        Select a configuration to begin editing columns.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-soft">
        Loading columns…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert tone="danger" heading="Unable to load columns" className="rounded-2xl">
        Please try again. If the issue persists, refresh the page.
      </Alert>
    );
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Column definitions</h2>
          <p className="text-sm text-slate-500">
            Define the export schema, display metadata, and script bindings for each canonical key.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => refetch()} disabled={replaceMutation.isPending}>
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            disabled={replaceMutation.isPending || validation.hasErrors || drafts.length === 0}
            isLoading={replaceMutation.isPending}
          >
            Save columns
          </Button>
        </div>
      </header>

      {successMessage ? (
        <Alert tone="success" heading={successMessage} />
      ) : null}

      <div className="space-y-4">
        {drafts.map((draft, index) => (
          <ColumnEditorRow
            key={draft.id}
            draft={draft}
            index={index}
            total={columnCount}
            errors={errors[draft.id] ?? {}}
            onChange={handleInputChange}
            onMove={handleMove}
            onRemove={handleRemove}
            onSelectScript={handleSelectScript}
            onManageScript={onManageScript}
            configurationId={configurationId}
            workspaceId={workspaceId}
          />
        ))}
      </div>

      <div className="flex justify-between border-t border-slate-200 pt-4">
        <div className="text-sm text-slate-500">
          {isDirty ? "Unsaved changes" : "All changes saved"}
        </div>
        <Button variant="ghost" onClick={handleAddColumn} size="sm">
          Add column
        </Button>
      </div>
    </section>
  );
}

interface ColumnEditorRowProps {
  readonly draft: ColumnDraft;
  readonly index: number;
  readonly total: number;
  readonly errors: ColumnDraftError;
  readonly onChange: (
    id: string,
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => void;
  readonly onMove: (id: string, direction: -1 | 1) => void;
  readonly onRemove: (id: string) => void;
  readonly onSelectScript: (id: string, scriptVersionId: string | null) => void;
  readonly onManageScript: (canonicalKey: string) => void;
  readonly workspaceId: string;
  readonly configurationId: string;
}

function ColumnEditorRow({
  draft,
  index,
  total,
  errors,
  onChange,
  onMove,
  onRemove,
  onSelectScript,
  onManageScript,
  workspaceId,
  configurationId,
}: ColumnEditorRowProps) {
  const canonicalKey = draft.canonicalKey.trim();
  const { data: scripts } = useScriptVersionsQuery(workspaceId, configurationId, canonicalKey);

  const selectedScript = scripts?.find((script) => script.script_version_id === draft.scriptVersionId);
  const hasValidationErrors = Boolean(selectedScript?.validation_errors);

  const handleSelectScriptVersion = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextValue = event.target.value || null;
    if (draft.scriptVersionId && draft.scriptVersionId !== nextValue) {
      const confirmed = window.confirm(
        "This column already has a bound script. Replacing it will update future runs. Continue?",
      );
      if (!confirmed) {
        event.preventDefault();
        return;
      }
    }
    onSelectScript(draft.id, nextValue);
  };

  const widthValue = draft.width;

  return (
    <article className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">
            {canonicalKey || "New column"} <span className="text-xs text-slate-400">#{index + 1}</span>
          </p>
          <p className="text-xs text-slate-500">
            Configure display metadata and optionally bind a configuration script version.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onMove(draft.id, -1)}
            disabled={index === 0}
            aria-label="Move column up"
          >
            ↑
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onMove(draft.id, 1)}
            disabled={index === total - 1}
            aria-label="Move column down"
          >
            ↓
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onRemove(draft.id)} aria-label="Remove column">
            Remove
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <FormField label="Canonical key" required error={errors.canonicalKey}>
          <Input
            name="canonicalKey"
            value={draft.canonicalKey}
            onChange={(event) => onChange(draft.id, event)}
            placeholder="Example: invoice_number"
          />
        </FormField>
        <FormField label="Display label" required error={errors.displayLabel}>
          <Input
            name="displayLabel"
            value={draft.displayLabel}
            onChange={(event) => onChange(draft.id, event)}
            placeholder="Example: Invoice Number"
          />
        </FormField>
        <FormField label="Header color" hint="Optional hex or tailwind token">
          <Input
            name="headerColor"
            value={draft.headerColor}
            onChange={(event) => onChange(draft.id, event)}
            placeholder="#2563eb"
          />
        </FormField>
        <FormField label="Column width" hint="Pixels" error={errors.width}>
          <Input
            name="width"
            type="number"
            min={0}
            value={widthValue}
            onChange={(event) => onChange(draft.id, event)}
          />
        </FormField>
      </div>

      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            name="required"
            checked={draft.required}
            onChange={(event) => onChange(draft.id, event)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          Required
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            name="enabled"
            checked={draft.enabled}
            onChange={(event) => onChange(draft.id, event)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          Enabled
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <FormField
          label="Bound script version"
          hint={canonicalKey ? "Select a script version to run for this column." : "Enter a canonical key to manage scripts."}
        >
          <Select
            name="scriptVersionId"
            value={draft.scriptVersionId ?? ""}
            onChange={handleSelectScriptVersion}
            disabled={!canonicalKey}
          >
            <option value="">No script</option>
            {(scripts ?? []).map((script) => (
              <option key={script.script_version_id} value={script.script_version_id}>
                {formatScriptOption(script)}
              </option>
            ))}
          </Select>
        </FormField>
        <div className="flex items-end justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => canonicalKey && onManageScript(canonicalKey)}
            disabled={!canonicalKey}
          >
            Manage scripts
          </Button>
        </div>
      </div>

      {hasValidationErrors ? (
        <Alert tone="warning" heading="Bound script reported validation errors.">
          Review the script output and fix issues before activating this configuration.
        </Alert>
      ) : null}

      <FormField label="Column parameters" hint="JSON payload" error={errors.paramsText}>
        <TextArea
          name="paramsText"
          value={draft.paramsText}
          onChange={(event) => onChange(draft.id, event)}
          rows={6}
          className="font-mono"
        />
      </FormField>
    </article>
  );
}

function validateDrafts(drafts: readonly ColumnDraft[]) {
  const fieldErrors: Record<string, ColumnDraftError> = {};
  const seenKeys = new Map<string, number>();
  const paramsById: Record<string, Record<string, unknown>> = {};
  let hasErrors = false;

  drafts.forEach((draft, index) => {
    const errors: ColumnDraftError = {};
    const trimmedKey = draft.canonicalKey.trim();
    if (!trimmedKey) {
      errors.canonicalKey = "Canonical key is required.";
    } else if (!/^[a-z0-9_\-]+$/i.test(trimmedKey)) {
      errors.canonicalKey = "Use letters, numbers, underscores, or hyphens.";
    }

    if (trimmedKey) {
      if (seenKeys.has(trimmedKey) && seenKeys.get(trimmedKey) !== index) {
        errors.canonicalKey = "Canonical key must be unique.";
        const firstIndex = seenKeys.get(trimmedKey);
        if (typeof firstIndex === "number") {
          fieldErrors[drafts[firstIndex].id] = {
            ...(fieldErrors[drafts[firstIndex].id] ?? {}),
            canonicalKey: "Canonical key must be unique.",
          };
        }
      }
      seenKeys.set(trimmedKey, index);
    }

    if (!draft.displayLabel.trim()) {
      errors.displayLabel = "Display label is required.";
    }

    if (draft.width) {
      const widthNumber = Number(draft.width);
      if (!Number.isFinite(widthNumber) || widthNumber < 0) {
        errors.width = "Width must be zero or positive.";
      }
    }

    if (draft.paramsText) {
      try {
        const parsed = JSON.parse(draft.paramsText);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          errors.paramsText = "Provide a JSON object.";
        } else {
          paramsById[draft.id] = parsed as Record<string, unknown>;
        }
      } catch {
        errors.paramsText = "Invalid JSON.";
      }
    } else {
      paramsById[draft.id] = {};
    }

    if (Object.keys(errors).length > 0) {
      hasErrors = true;
      fieldErrors[draft.id] = errors;
    }
  });

  return { hasErrors, fieldErrors, paramsById };
}

function formatScriptOption(script: ConfigurationScriptVersion) {
  const status = script.validated_at
    ? "Validated"
    : script.validation_errors
      ? "Needs attention"
      : "Pending";
  return `v${script.version} • ${status}`;
}

function buildDraftId(column: ConfigurationColumn) {
  return `${column.configuration_id}:${column.canonical_key}`;
}

function createDraftId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `draft-${Math.random().toString(36).slice(2, 10)}`;
}

function formatParams(params: ConfigurationColumn["params"]) {
  try {
    return JSON.stringify(params ?? {}, null, 2);
  } catch {
    return "{}";
  }
}
