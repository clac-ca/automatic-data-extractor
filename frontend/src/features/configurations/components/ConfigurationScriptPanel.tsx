import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { ConfigurationScriptVersion } from "@types/configurations";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Select } from "@ui/select";
import { TextArea } from "@ui/input";
import { useScriptVersionsQuery } from "../hooks/useScriptVersionsQuery";
import { useScriptVersionQuery } from "../hooks/useScriptVersionQuery";
import { useCreateScriptVersionMutation } from "../hooks/useCreateScriptVersionMutation";
import { useValidateScriptVersionMutation } from "../hooks/useValidateScriptVersionMutation";

export interface ConfigurationScriptPanelProps {
  readonly workspaceId: string;
  readonly configurationId: string | null;
  readonly canonicalKey: string | null;
  readonly selectedScriptVersionId: string | null;
  readonly onSelectScriptVersion: (scriptVersionId: string | null) => void;
}

export function ConfigurationScriptPanel({
  workspaceId,
  configurationId,
  canonicalKey,
  selectedScriptVersionId,
  onSelectScriptVersion,
}: ConfigurationScriptPanelProps) {
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState("");
  const [creationMessage, setCreationMessage] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  const hasSelectionContext = Boolean(configurationId && canonicalKey);
  const { data: versions, isLoading, isError } = useScriptVersionsQuery(
    workspaceId,
    configurationId ?? "",
    canonicalKey ?? "",
  );

  const sortedVersions = useMemo(() => {
    return [...(versions ?? [])].sort((a, b) => b.version - a.version);
  }, [versions]);

  const activeScriptId = selectedScriptVersionId ?? sortedVersions[0]?.script_version_id ?? null;
  const docstringPreview = useMemo(() => parseDocstringMetadata(code), [code]);

  useEffect(() => {
    if (canonicalKey && code.trim().length === 0) {
      setCode(buildScriptTemplate(canonicalKey));
    }
  }, [canonicalKey]);

  useEffect(() => {
    if (hasSelectionContext && !selectedScriptVersionId && sortedVersions[0]) {
      onSelectScriptVersion(sortedVersions[0].script_version_id);
    }
  }, [hasSelectionContext, onSelectScriptVersion, selectedScriptVersionId, sortedVersions]);

  const { data: scriptDetail, isFetching: isFetchingDetail } = useScriptVersionQuery(
    workspaceId,
    configurationId ?? "",
    canonicalKey ?? "",
    activeScriptId,
    { includeCode: true },
  );

  const createMutation = useCreateScriptVersionMutation(
    workspaceId,
    configurationId ?? "",
    canonicalKey ?? "",
  );
  const validateMutation = useValidateScriptVersionMutation(
    workspaceId,
    configurationId ?? "",
    canonicalKey ?? "",
  );

  const handleCreateScript = async () => {
    if (!configurationId || !canonicalKey) {
      return;
    }

    setCreationMessage(null);
    try {
      const script = await createMutation.mutateAsync({
        canonical_key: canonicalKey,
        language,
        code,
      });
      setCreationMessage("Script version uploaded. Run validation to refresh metadata.");
      setCode(buildScriptTemplate(canonicalKey));
      onSelectScriptVersion(script.script_version_id);
    } catch (error) {
      console.error("Failed to create script version", error);
    }
  };

  const handleValidate = async () => {
    if (!activeScriptId || !scriptDetail) {
      return;
    }
    setValidationMessage(null);
    try {
      const script = await validateMutation.mutateAsync({
        scriptVersionId: activeScriptId,
        etag: scriptDetail.code_sha256,
      });
      setValidationMessage("Validation completed.");
      onSelectScriptVersion(script.script_version_id);
    } catch (error) {
      console.error("Failed to validate script", error);
    }
  };

  if (!configurationId) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
        Select a configuration to manage scripts.
      </div>
    );
  }

  if (!canonicalKey) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
        Choose a column to view and edit script versions.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-soft">
        Loading scripts…
      </div>
    );
  }

  if (isError) {
    return (
      <Alert tone="danger" heading="Unable to load script versions" className="rounded-2xl">
        Please try again. If the issue persists, refresh the page.
      </Alert>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Scripts for {canonicalKey}</h2>
        <p className="text-sm text-slate-500">
          Upload new versions, review validation status, and inspect parsed metadata.
        </p>
      </header>

      {creationMessage ? <Alert tone="success" heading={creationMessage} /> : null}
      {validationMessage ? <Alert tone="success" heading={validationMessage} /> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h3 className="text-sm font-semibold text-slate-800">Version history</h3>
          {sortedVersions.length === 0 ? (
            <p className="text-sm text-slate-500">No script versions yet. Upload code to create the first version.</p>
          ) : (
            <ul className="space-y-2">
              {sortedVersions.map((script) => {
                const isSelected = script.script_version_id === activeScriptId;
                return (
                  <li key={script.script_version_id}>
                    <button
                      type="button"
                      onClick={() => onSelectScriptVersion(script.script_version_id)}
                      className={`w-full rounded-xl border p-3 text-left transition ${
                        isSelected
                          ? "border-brand-400 bg-brand-50"
                          : "border-slate-200 bg-white hover:border-brand-300 hover:bg-brand-50/60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">Version {script.version}</p>
                          <p className="text-xs text-slate-500">Uploaded {formatRelative(script.created_at)}</p>
                        </div>
                        <ScriptStatusBadge script={script} />
                      </div>
                      {script.doc_description ? (
                        <p className="mt-2 text-xs text-slate-500">{script.doc_description}</p>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <h3 className="text-sm font-semibold text-slate-800">Upload new version</h3>
          <FormField label="Language">
            <Select value={language} onChange={(event) => setLanguage(event.target.value)}>
              <option value="python">Python</option>
            </Select>
          </FormField>
          <FormField label="Script code" hint="Include the docstring with name, description, and version fields.">
            <TextArea value={code} onChange={(event) => setCode(event.target.value)} rows={12} className="font-mono" />
          </FormField>
          <DocstringPreview metadata={docstringPreview} />
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Preview</h4>
            <pre
              className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-100"
              dangerouslySetInnerHTML={{ __html: highlightPython(code) }}
            />
          </div>
          <div className="flex justify-end">
            <Button
              variant="primary"
              size="sm"
              onClick={handleCreateScript}
              disabled={createMutation.isPending || code.trim().length === 0}
              isLoading={createMutation.isPending}
            >
              Upload version
            </Button>
          </div>
        </div>
      </div>

      {activeScriptId ? (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Selected version</h3>
              <p className="text-xs text-slate-500">Review metadata, docstring fields, and validation results.</p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleValidate}
              disabled={validateMutation.isPending || !scriptDetail}
              isLoading={validateMutation.isPending}
            >
              Re-run validation
            </Button>
          </header>
          <div className="grid gap-4 md:grid-cols-2">
            <InfoRow label="Version">{scriptDetail?.version ?? "—"}</InfoRow>
            <InfoRow label="SHA256">{scriptDetail?.code_sha256 ?? "—"}</InfoRow>
            <InfoRow label="Doc name">{scriptDetail?.doc_name ?? "—"}</InfoRow>
            <InfoRow label="Doc version">{scriptDetail?.doc_declared_version ?? "—"}</InfoRow>
            <InfoRow label="Validated at">{scriptDetail?.validated_at ? formatTimestamp(scriptDetail.validated_at) : "Never"}</InfoRow>
            <InfoRow label="Created at">{scriptDetail ? formatTimestamp(scriptDetail.created_at) : "—"}</InfoRow>
          </div>
          {scriptDetail?.validation_errors ? (
            <Alert tone="warning" heading="Validation errors detected">
              <pre className="mt-2 overflow-auto rounded bg-slate-900/80 p-3 text-xs text-slate-100">
                {JSON.stringify(scriptDetail.validation_errors, null, 2)}
              </pre>
            </Alert>
          ) : null}
          <FormField label="Script code" hint={isFetchingDetail ? "Refreshing…" : undefined}>
            <TextArea value={scriptDetail?.code ?? ""} readOnly rows={16} className="font-mono" />
          </FormField>
        </div>
      ) : null}
    </section>
  );
}

function ScriptStatusBadge({ script }: { readonly script: ConfigurationScriptVersion }) {
  let tone = "bg-slate-200 text-slate-700";
  let label = "Pending";
  if (script.validation_errors) {
    tone = "bg-warning-100 text-warning-700";
    label = "Needs attention";
  } else if (script.validated_at) {
    tone = "bg-emerald-100 text-emerald-700";
    label = "Validated";
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>
      {label}
    </span>
  );
}

function InfoRow({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm text-slate-800">{children}</p>
    </div>
  );
}

function formatTimestamp(value: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
      new Date(value),
    );
  } catch {
    return value;
  }
}

function formatRelative(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const diff = date.getTime() - Date.now();
  const days = Math.round(diff / (1000 * 60 * 60 * 24));
  return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(days, "day");
}

function buildScriptTemplate(canonicalKey: string) {
  return [
    '"""',
    `name: ${canonicalKey}`,
    "description: Describe what this script detects.",
    "version: 1",
    '"""',
    "",
    "def detect_sample(*, header=None, values=None, state=None, **_):",
    '    """Replace with real detection logic."""',
    '    return {"scores": {"self": 1.0 if values else 0.0}}',
    "",
  ].join("\n");
}

interface DocstringMetadata {
  name?: string;
  description?: string;
  version?: string;
}

function DocstringPreview({ metadata }: { readonly metadata: DocstringMetadata | null }) {
  if (!metadata) {
    return (
      <Alert tone="info" heading="Docstring preview">
        Add a triple-quoted docstring at the top of the file to populate script name, description, and version.
      </Alert>
    );
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Docstring preview</h4>
      <dl className="mt-2 grid gap-2 md:grid-cols-2">
        <DocstringRow label="Name">{metadata.name ?? "—"}</DocstringRow>
        <DocstringRow label="Version">{metadata.version ?? "—"}</DocstringRow>
        <DocstringRow label="Description" className="md:col-span-2">
          {metadata.description ?? "—"}
        </DocstringRow>
      </dl>
    </div>
  );
}

function DocstringRow({
  label,
  children,
  className,
}: {
  readonly label: string;
  readonly children: ReactNode;
  readonly className?: string;
}) {
  return (
    <div className={className}>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-700">{children}</dd>
    </div>
  );
}

function parseDocstringMetadata(code: string): DocstringMetadata | null {
  const match = code.match(/"""([\s\S]*?)"""/);
  if (!match) {
    return null;
  }
  const lines = match[1]
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  if (lines.length === 0) {
    return null;
  }
  const metadata: DocstringMetadata = {};
  for (const line of lines) {
    const [key, ...rest] = line.split(":");
    if (!key || rest.length === 0) {
      continue;
    }
    const value = rest.join(":").trim();
    const normalizedKey = key.trim().toLowerCase();
    if (normalizedKey === "name") {
      metadata.name = value;
    } else if (normalizedKey === "description") {
      metadata.description = value;
    } else if (normalizedKey === "version") {
      metadata.version = value;
    }
  }
  return metadata;
}

function highlightPython(source: string) {
  const escaped = escapeHtml(source);
  const withDocstring = escaped.replace(/"""([\s\S]*?)"""/g, (match) => `<span class="text-amber-200">${match}</span>`);
  const withStrings = withDocstring.replace(/'(.*?)'/g, (match) => `<span class="text-emerald-200">${match}</span>`);
  const withKeywords = withStrings.replace(
    /\b(def|return|import|from|for|while|if|else|elif|try|except|class|async|await)\b/g,
    (match) => `<span class="text-sky-300">${match}</span>`,
  );
  const withComments = withKeywords.replace(/#([^\n]*)/g, (match) => `<span class="text-slate-400">${match}</span>`);
  return withComments;
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
