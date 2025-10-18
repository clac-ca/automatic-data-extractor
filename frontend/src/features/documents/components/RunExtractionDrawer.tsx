import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import type { DocumentRecord } from "../../../shared/types/documents";
import type { JobRecord } from "../../../shared/types/jobs";
import { useConfigurationsQuery } from "../../configurations/hooks/useConfigurationsQuery";
import { useSubmitJobMutation } from "../../jobs/hooks/useJobs";
import { useDocumentRunPreferences } from "../hooks/useDocumentRunPreferences";
import { Alert } from "../../../ui/alert";
import { Button } from "../../../ui/button";
import { Select } from "../../../ui/select";

interface RunExtractionDrawerProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord | null;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
}

export function RunExtractionDrawer({
  open,
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
}: RunExtractionDrawerProps) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const originalOverflow = window.document.body.style.overflow;
    window.document.body.style.overflow = "hidden";
    return () => {
      window.document.body.style.overflow = originalOverflow;
    };
  }, [open]);

  if (typeof window === "undefined" || !open || !documentRecord) {
    return null;
  }

  return createPortal(
    <RunExtractionDrawerContent
      workspaceId={workspaceId}
      documentRecord={documentRecord}
      onClose={onClose}
      onRunSuccess={onRunSuccess}
      onRunError={onRunError}
    />,
    window.document.body,
  );
}

interface DrawerContentProps {
  readonly workspaceId: string;
  readonly documentRecord: DocumentRecord;
  readonly onClose: () => void;
  readonly onRunSuccess?: (job: JobRecord) => void;
  readonly onRunError?: (message: string) => void;
}

function RunExtractionDrawerContent({
  workspaceId,
  documentRecord,
  onClose,
  onRunSuccess,
  onRunError,
}: DrawerContentProps) {
  const configurationsQuery = useConfigurationsQuery(workspaceId);
  const submitJob = useSubmitJobMutation(workspaceId);
  const { preferences, setPreferences } = useDocumentRunPreferences(
    workspaceId,
    documentRecord.document_id,
  );

  const configurations = configurationsQuery.data ?? [];
  const activeConfiguration = useMemo(
    () => configurations.find((configuration) => configuration.is_active) ?? null,
    [configurations],
  );

  const [selectedConfigurationId, setSelectedConfigurationId] = useState<string | "">(
    preferences.configurationId ?? activeConfiguration?.configuration_id ?? "",
  );

  useEffect(() => {
    setSelectedConfigurationId(
      preferences.configurationId ?? activeConfiguration?.configuration_id ?? "",
    );
  }, [preferences.configurationId, activeConfiguration?.configuration_id]);

  const selectedConfiguration = configurations.find(
    (configuration) => configuration.configuration_id === selectedConfigurationId,
  );

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const hasConfigurations = configurations.length > 0;

  const handleSubmit = () => {
    if (!selectedConfiguration) {
      setErrorMessage("Select a configuration before running the extractor.");
      return;
    }
    setErrorMessage(null);
    submitJob.mutate(
      {
        input_document_id: documentRecord.document_id,
        configuration_id: selectedConfiguration.configuration_id,
        configuration_version: selectedConfiguration.version,
      },
      {
        onSuccess: (job) => {
          setPreferences({
            configurationId: selectedConfiguration.configuration_id,
            configurationVersion: selectedConfiguration.version,
          });
          onRunSuccess?.(job);
          onClose();
        },
        onError: (error) => {
          const message =
            error instanceof Error
              ? error.message
              : "Unable to submit extraction job.";
          setErrorMessage(message);
          onRunError?.(message);
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        className="flex-1 bg-slate-900/30 backdrop-blur-sm"
        aria-label="Close run settings"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-[min(28rem,92vw)] flex-col border-l border-slate-200 bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Run extraction</h2>
            <p className="text-xs text-slate-500">Prepare and submit a processing job.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitJob.isPending}>
            Close
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-sm text-slate-600">
          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Document
            </p>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-800" title={documentRecord.name}>
                {documentRecord.name}
              </p>
              <p className="text-xs text-slate-500">Uploaded {new Date(documentRecord.created_at).toLocaleString()}</p>
              {documentRecord.last_run_at ? (
                <p className="text-xs text-slate-500">
                  Last run {new Date(documentRecord.last_run_at).toLocaleString()}
                </p>
              ) : null}
            </div>
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Configuration
            </p>
            {configurationsQuery.isLoading ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Loading configurations…
              </div>
            ) : configurationsQuery.isError ? (
              <Alert tone="danger">
                Unable to load configurations. {" "}
                {configurationsQuery.error instanceof Error ? configurationsQuery.error.message : "Try again later."}
              </Alert>
            ) : hasConfigurations ? (
              <Select
                value={selectedConfigurationId}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelectedConfigurationId(value);
                  if (value) {
                    const target = configurations.find(
                      (configuration) => configuration.configuration_id === value,
                    );
                    if (target) {
                      setPreferences({
                        configurationId: target.configuration_id,
                        configurationVersion: target.version,
                      });
                    }
                  }
                }}
                disabled={submitJob.isPending}
              >
                <option value="">Select configuration</option>
                {configurations.map((configuration) => (
                  <option key={configuration.configuration_id} value={configuration.configuration_id}>
                    {configuration.title} (v{configuration.version})
                    {configuration.is_active ? " • Active" : ""}
                  </option>
                ))}
              </Select>
            ) : (
              <Alert tone="info">No configurations available. Create one before running extraction.</Alert>
            )}
          </section>

          <section className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Advanced options
            </p>
            <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Sheet selection and advanced flags will appear here once the processor supports them.
            </p>
          </section>

          {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={submitJob.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            isLoading={submitJob.isPending}
            disabled={!hasConfigurations || submitJob.isPending}
          >
            Run extraction
          </Button>
        </footer>
      </aside>
    </div>
  );
}
