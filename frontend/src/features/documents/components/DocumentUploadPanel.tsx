import { useCallback, useEffect, useMemo, useState } from "react";

import { describeConfiguration, type ConfigurationRecord } from "../../../api/configurations";
import { useUploadDocumentMutation } from "../../../app/documents/hooks";
import { useToast } from "../../../components/ToastProvider";
import { formatByteSize } from "../../../utils/format";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

type UploadStatus = "queued" | "uploading" | "uploaded" | "error";

interface QueuedFile {
  id: string;
  file: File;
  status: UploadStatus;
  errorMessage: string | null;
}

function createUploadId(file: File) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${file.name}-${file.size}-${file.lastModified}`;
}

function getDefaultExpiryDate() {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  return date.toISOString().slice(0, 10);
}

interface DocumentUploadPanelProps {
  workspaceId: string;
  documentType: string | null;
  configurations: ConfigurationRecord[];
}

export function DocumentUploadPanel({
  workspaceId,
  documentType,
  configurations,
}: DocumentUploadPanelProps) {
  const { pushToast } = useToast();
  const uploadMutation = useUploadDocumentMutation();

  const matchingConfigurations = useMemo(
    () =>
      configurations.filter(
        (configuration) => configuration.document_type === documentType,
      ),
    [configurations, documentType],
  );

  const [queuedFiles, setQueuedFiles] = useState<QueuedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [expiresAt, setExpiresAt] = useState(getDefaultExpiryDate);
  const [metadataInput, setMetadataInput] = useState("{}");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [selectedConfigurationIds, setSelectedConfigurationIds] = useState<string[]>([]);

  const defaultConfigurationIds = useMemo(() => {
    const active = matchingConfigurations
      .filter((configuration) => configuration.is_active)
      .map((configuration) => configuration.configuration_id);
    if (active.length > 0) {
      return active;
    }
    if (matchingConfigurations.length > 0) {
      return [matchingConfigurations[0].configuration_id];
    }
    return [];
  }, [matchingConfigurations]);

  const readyToUpload = Boolean(documentType && queuedFiles.length > 0);

  const toggleConfiguration = (id: string) => {
    setSelectedConfigurationIds((current) => {
      if (current.includes(id)) {
        return current.filter((value) => value !== id);
      }
      return [...current, id];
    });
  };

  const resetConfigurationSelection = useCallback(() => {
    setSelectedConfigurationIds(defaultConfigurationIds);
  }, [defaultConfigurationIds]);

  useEffect(() => {
    resetConfigurationSelection();
  }, [resetConfigurationSelection]);

  const updateFile = useCallback((id: string, updates: Partial<QueuedFile>) => {
    setQueuedFiles((files) =>
      files.map((file) => (file.id === id ? { ...file, ...updates } : file)),
    );
  }, []);

  const removeFile = (id: string) => {
    setQueuedFiles((files) => files.filter((file) => file.id !== id));
  };

  const handleFilesAdded = useCallback(
    (files: FileList | File[]) => {
      if (!documentType) {
        pushToast({
          tone: "error",
          title: "Select a document type",
          description: "Choose a document type before uploading files.",
        });
        return;
      }

      const next: QueuedFile[] = [];
      Array.from(files).forEach((file) => {
        if (file.size > MAX_UPLOAD_BYTES) {
          pushToast({
            tone: "error",
            title: "File too large",
            description: `${file.name} exceeds the ${formatByteSize(MAX_UPLOAD_BYTES)} limit`,
          });
          return;
        }
        next.push({
          id: createUploadId(file),
          file,
          status: "queued",
          errorMessage: null,
        });
      });

      if (next.length > 0) {
        setQueuedFiles((current) => [...current, ...next]);
      }
    },
    [documentType, pushToast],
  );

  const handleDragOver = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files) {
      handleFilesAdded(event.dataTransfer.files);
    }
  };

  const handleSubmit = async () => {
    if (!documentType || queuedFiles.length === 0) {
      pushToast({
        tone: "error",
        title: "Nothing to upload",
        description: "Add files and choose a document type first.",
      });
      return;
    }

    let metadata: Record<string, unknown> = {};
    const trimmed = metadataInput.trim();
    if (trimmed) {
      try {
        metadata = JSON.parse(trimmed) as Record<string, unknown>;
      } catch (error) {
        pushToast({
          tone: "error",
          title: "Metadata must be JSON",
          description: "Fix the JSON before uploading.",
        });
        return;
      }
    }

    const targetConfigurationIds = selectedConfigurationIds.length
      ? selectedConfigurationIds
      : defaultConfigurationIds;

    for (const item of queuedFiles) {
      updateFile(item.id, { status: "uploading", errorMessage: null });
      try {
        await uploadMutation.mutateAsync({
          workspaceId,
          file: item.file,
          options: {
            documentType,
            expiresAt,
            metadata,
            configurationIds: targetConfigurationIds,
          },
        });
        updateFile(item.id, { status: "uploaded" });
      } catch (error) {
        updateFile(item.id, {
          status: "error",
          errorMessage: error instanceof Error ? error.message : "Upload failed",
        });
      }
    }
  };

  return (
    <section className="card document-upload">
      <header>
        <h2 className="card-title">Upload documents</h2>
        <p className="page-subtitle">
          Drag and drop files or browse to add documents to the selected type.
        </p>
      </header>
      <div>
        <label
          htmlFor="document-upload-input"
          className={`dropzone${isDragging ? " is-dragging" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <strong>Drop files here</strong>
          <p className="page-subtitle">or click to browse</p>
          <input
            id="document-upload-input"
            type="file"
            multiple
            hidden
            onChange={(event) => {
              if (event.target.files) {
                handleFilesAdded(event.target.files);
              }
            }}
          />
        </label>
      </div>
      {queuedFiles.length > 0 ? (
        <ul className="queue-list">
          {queuedFiles.map((item) => (
            <li key={item.id} className="queue-item">
              <div>
                <div>{item.file.name}</div>
                <div className="queue-item-status">
                  {item.status === "queued" && "Queued"}
                  {item.status === "uploading" && "Uploading"}
                  {item.status === "uploaded" && "Uploaded"}
                  {item.status === "error" && item.errorMessage}
                </div>
              </div>
              <div className="inline-actions">
                {item.status !== "uploading" ? (
                  <button
                    type="button"
                    className="button-ghost"
                    onClick={() => removeFile(item.id)}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-state">No files queued yet.</div>
      )}
      <div className="form-grid">
        <label>
          <span className="muted">Expires on</span>
          <input
            className="input"
            type="date"
            value={expiresAt}
            min={new Date().toISOString().slice(0, 10)}
            onChange={(event) => setExpiresAt(event.target.value)}
          />
        </label>
        <label>
          <span className="muted">Metadata (JSON)</span>
          <textarea
            className="textarea"
            rows={4}
            value={metadataInput}
            onChange={(event) => setMetadataInput(event.target.value)}
          />
        </label>
      </div>
      <div>
        <button
          type="button"
          className="button-ghost"
          onClick={() => setAdvancedOpen((value) => !value)}
        >
          {advancedOpen ? "Hide" : "Show"} advanced options
        </button>
        {advancedOpen ? (
          <div className="advanced-options">
            <div className="inline-actions">
              <button type="button" className="button-secondary" onClick={resetConfigurationSelection}>
                Use defaults
              </button>
            </div>
            {matchingConfigurations.length === 0 ? (
              <p className="muted">No configurations available for this document type.</p>
            ) : (
              <div className="form-grid">
                {matchingConfigurations.map((configuration) => {
                  const id = configuration.configuration_id;
                  return (
                    <label key={id} className="inline-actions">
                      <input
                        type="checkbox"
                        checked={selectedConfigurationIds.includes(id)}
                        onChange={() => toggleConfiguration(id)}
                      />
                      <span>{describeConfiguration(configuration)}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        ) : null}
      </div>
      <div className="inline-actions">
        <button
          type="button"
          className="button-primary"
          onClick={handleSubmit}
          disabled={!readyToUpload || uploadMutation.isPending}
        >
          {uploadMutation.isPending ? "Uploading…" : "Upload files"}
        </button>
      </div>
    </section>
  );
}
