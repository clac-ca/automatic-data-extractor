import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { Link, useParams } from "react-router-dom";

import { useWorkspaceContextQuery } from "../app/workspaces/hooks";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";
import {
  useActiveConfigurationsQuery,
  useDeleteDocumentMutation,
  useUploadDocumentMutation,
  useWorkspaceDocumentsQuery,
} from "../app/documents/hooks";
import {
  describeConfiguration,
  uniqueDocumentTypes,
} from "../api/configurations";
import { buildDocumentDownloadUrl } from "../api/documents";
import { normaliseErrorMessage } from "../api/errors";
import { useToast } from "../components/ToastProvider";
import {
  formatByteSize,
  formatDateTime,
  formatDocumentStatus,
} from "../utils/format";

const DOCUMENT_TYPE_STORAGE_PREFIX = "ade.workspace.documentType.";
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // 50 MB

type UploadStatus = "queued" | "uploading" | "uploaded" | "error";

interface QueuedUpload {
  id: string;
  file: File;
  status: UploadStatus;
  errorMessage: string | null;
}

function createUploadId(file: File): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(16).slice(2)}`;
}

function defaultExpiryDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  return date.toISOString().slice(0, 10);
}

export function WorkspaceDocumentsPage() {
  const { workspaceId } = useParams();
  const { pushToast } = useToast();
  const { setSelectedWorkspaceId } = useWorkspaceSelection();
  const { data: workspaceContext, isLoading: isWorkspaceLoading } =
    useWorkspaceContextQuery(workspaceId ?? null);
  const workspace = workspaceContext?.workspace;
  const resolvedWorkspaceId = workspace?.workspace_id ?? null;

  useEffect(() => {
    if (resolvedWorkspaceId) {
      setSelectedWorkspaceId(resolvedWorkspaceId);
    }
  }, [resolvedWorkspaceId, setSelectedWorkspaceId]);

  const {
    data: configurations,
    isLoading: isConfigurationsLoading,
  } = useActiveConfigurationsQuery(resolvedWorkspaceId);

  const documentTypeOptions = useMemo(
    () => uniqueDocumentTypes(configurations ?? []),
    [configurations],
  );

  const [selectedDocumentType, setSelectedDocumentType] = useState<string | null>(null);

  useEffect(() => {
    if (!resolvedWorkspaceId) {
      return;
    }
    const storageKey = `${DOCUMENT_TYPE_STORAGE_PREFIX}${resolvedWorkspaceId}`;
    const stored = window.localStorage.getItem(storageKey);
    if (stored) {
      setSelectedDocumentType(stored);
    }
  }, [resolvedWorkspaceId]);

  useEffect(() => {
    if (!resolvedWorkspaceId) {
      return;
    }
    if (!documentTypeOptions.length) {
      setSelectedDocumentType(null);
      return;
    }
    setSelectedDocumentType((current) => {
      if (current && documentTypeOptions.includes(current)) {
        return current;
      }
      return documentTypeOptions[0] ?? null;
    });
  }, [documentTypeOptions, resolvedWorkspaceId]);

  useEffect(() => {
    if (!resolvedWorkspaceId) {
      return;
    }
    const storageKey = `${DOCUMENT_TYPE_STORAGE_PREFIX}${resolvedWorkspaceId}`;
    if (selectedDocumentType) {
      window.localStorage.setItem(storageKey, selectedDocumentType);
    } else {
      window.localStorage.removeItem(storageKey);
    }
  }, [resolvedWorkspaceId, selectedDocumentType]);

  const {
    data: documents,
    isLoading: isDocumentsLoading,
    isFetching: isDocumentsFetching,
  } = useWorkspaceDocumentsQuery(resolvedWorkspaceId, selectedDocumentType);

  const uploadMutation = useUploadDocumentMutation();
  const deleteMutation = useDeleteDocumentMutation();

  const [uploads, setUploads] = useState<QueuedUpload[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [metadataInput, setMetadataInput] = useState("{}");
  const [expiryDate, setExpiryDate] = useState(defaultExpiryDate);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [metadataDocumentId, setMetadataDocumentId] = useState<string | null>(null);
  const [selectedConfigurationIds, setSelectedConfigurationIds] = useState<string[]>([]);

  const matchingConfigurations = useMemo(() => {
    if (!selectedDocumentType) {
      return [];
    }
    return (configurations ?? []).filter(
      (configuration) => configuration.document_type === selectedDocumentType,
    );
  }, [configurations, selectedDocumentType]);

  useEffect(() => {
    if (!selectedDocumentType) {
      setSelectedConfigurationIds([]);
      return;
    }
    const available = matchingConfigurations.map(
      (configuration) => configuration.configuration_id,
    );
    setSelectedConfigurationIds((current) => {
      const existing = current.filter((id) => available.includes(id));
      if (existing.length > 0) {
        return existing;
      }
      if (available.length > 0) {
        return [available[0]];
      }
      return [];
    });
  }, [matchingConfigurations, selectedDocumentType]);

  const workspaceDocuments = useMemo(
    () => documents ?? [],
    [documents],
  );
  const hasActiveConfigurations = documentTypeOptions.length > 0;

  const updateUpload = useCallback((id: string, updates: Partial<QueuedUpload>) => {
    setUploads((items) =>
      items.map((item) => (item.id === id ? { ...item, ...updates } : item)),
    );
  }, []);

  const handleFilesAdded = useCallback(
    (files: FileList | File[]) => {
      if (!hasActiveConfigurations || !selectedDocumentType) {
        pushToast({
          tone: "error",
          title: "Select a document type",
          description: "Choose a document type before adding files.",
        });
        return;
      }
      const nextUploads: QueuedUpload[] = [];
      Array.from(files).forEach((file) => {
        if (file.size > MAX_UPLOAD_BYTES) {
          pushToast({
            tone: "error",
            title: "File too large",
            description: `${file.name} exceeds the ${formatByteSize(MAX_UPLOAD_BYTES)} limit.`,
          });
          return;
        }
        nextUploads.push({
          id: createUploadId(file),
          file,
          status: "queued",
          errorMessage: null,
        });
      });
      if (nextUploads.length > 0) {
        setUploads((current) => [...current, ...nextUploads]);
      }
    },
    [hasActiveConfigurations, pushToast, selectedDocumentType],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLLabelElement>) => {
      event.preventDefault();
      setIsDragging(false);
      if (event.dataTransfer?.files) {
        handleFilesAdded(event.dataTransfer.files);
      }
    },
    [handleFilesAdded],
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    if (!isDragging) {
      setIsDragging(true);
    }
  }, [isDragging]);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      if (event.target.files) {
        handleFilesAdded(event.target.files);
        event.target.value = "";
      }
    },
    [handleFilesAdded],
  );

  const handleRemoveUpload = useCallback((id: string) => {
    setUploads((items) => items.filter((item) => item.id !== id));
  }, []);

  const handleDeleteDocument = useCallback(
    async (documentId: string) => {
      if (!resolvedWorkspaceId) {
        return;
      }
      const confirmed = window.confirm(
        "Remove this document from the workspace? This keeps the audit trail but hides it from analysts.",
      );
      if (!confirmed) {
        return;
      }
      await deleteMutation.mutateAsync({
        workspaceId: resolvedWorkspaceId,
        documentId,
      });
    },
    [deleteMutation, resolvedWorkspaceId],
  );

  const handleUploadAll = useCallback(async () => {
    if (!resolvedWorkspaceId || !selectedDocumentType) {
      pushToast({
        tone: "error",
        title: "Document type required",
        description: "Select a document type before uploading.",
      });
      return;
    }
    if (uploads.length === 0) {
      pushToast({
        tone: "error",
        title: "No files queued",
        description: "Add at least one file to upload.",
      });
      return;
    }

    let parsedMetadata: Record<string, unknown> = {};
    const trimmed = metadataInput.trim();
    if (trimmed) {
      try {
        parsedMetadata = JSON.parse(trimmed);
        if (typeof parsedMetadata !== "object" || Array.isArray(parsedMetadata)) {
          throw new Error("Metadata must be a JSON object.");
        }
      } catch (error) {
        pushToast({
          tone: "error",
          title: "Invalid metadata",
          description: normaliseErrorMessage(error),
        });
        return;
      }
    }

    for (const upload of uploads) {
      if (upload.status === "uploaded" || upload.status === "uploading") {
        continue;
      }
      updateUpload(upload.id, { status: "uploading", errorMessage: null });
      try {
        await uploadMutation.mutateAsync({
          workspaceId: resolvedWorkspaceId,
          file: upload.file,
          options: {
            documentType: selectedDocumentType,
            metadata: parsedMetadata,
            expiresAt: expiryDate || null,
            configurationIds: selectedConfigurationIds,
          },
        });
        updateUpload(upload.id, { status: "uploaded", errorMessage: null });
      } catch (error) {
        updateUpload(upload.id, {
          status: "error",
          errorMessage: normaliseErrorMessage(error),
        });
      }
    }
  }, [
    expiryDate,
    metadataInput,
    pushToast,
    resolvedWorkspaceId,
    selectedConfigurationIds,
    selectedDocumentType,
    updateUpload,
    uploadMutation,
    uploads,
  ]);

  const isUploading = uploadMutation.isPending;
  const isUploadDisabled =
    !resolvedWorkspaceId ||
    !selectedDocumentType ||
    !hasActiveConfigurations ||
    uploads.length === 0 ||
    isUploading;

  const activeDocument = useMemo(
    () => workspaceDocuments.find((document) => document.id === metadataDocumentId) ?? null,
    [metadataDocumentId, workspaceDocuments],
  );

  if (!workspaceId) {
    return (
      <div className="page">
        <h1 className="page-title">Workspace not specified</h1>
        <p>Select a workspace to upload documents.</p>
        <Link to="/workspaces">Return to workspaces</Link>
      </div>
    );
  }

  if (isWorkspaceLoading) {
    return (
      <div className="page">
        <h1 className="page-title">Preparing uploads…</h1>
        <p className="muted">Loading workspace configuration.</p>
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="page">
        <h1 className="page-title">Workspace not found</h1>
        <p>Check the URL and try again.</p>
        <Link to="/workspaces">Return to workspaces</Link>
      </div>
    );
  }

  return (
    <div className="page documents-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Upload documents</h1>
          <p className="page-intro">
            Upload files to extract structured data for {workspace.name}. Start by
            confirming the document type that best matches your files.
          </p>
        </div>
      </header>

      <section className="section">
        <header className="section-header">
          <h2>Document type</h2>
          <span className="muted">
            Choose the template that matches your files. This controls validation and routing.
          </span>
        </header>
        <div className="form-field">
          <label className="form-label" htmlFor="document-type">
            Document type
          </label>
          <select
            id="document-type"
            className="form-select"
            value={selectedDocumentType ?? ""}
            onChange={(event) => setSelectedDocumentType(event.target.value || null)}
            disabled={!documentTypeOptions.length}
          >
            {documentTypeOptions.length === 0 ? (
              <option value="">No active document types</option>
            ) : null}
            {documentTypeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        {!hasActiveConfigurations && !isConfigurationsLoading ? (
          <p className="muted">
            No active configurations are available for this workspace. Uploads are disabled until a configuration is published.
          </p>
        ) : null}
      </section>

      <section className="section">
        <header className="section-header">
          <h2>Upload files</h2>
        </header>
        <label
          className={`uploader ${isDragging ? "uploader--dragging" : ""}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <input
            className="uploader-input"
            type="file"
            multiple
            onChange={handleFileInputChange}
            disabled={!hasActiveConfigurations}
          />
          <span>Drag and drop files here, or click to browse.</span>
        </label>
        <p className="muted">
          Supported formats: PDF, XLSX, CSV. Maximum size {formatByteSize(MAX_UPLOAD_BYTES)} per file.
        </p>

        {uploads.length > 0 ? (
          <div className="upload-queue">
            {uploads.map((item) => (
              <div key={item.id} className="upload-item">
                <div className="upload-item-details">
                  <strong>{item.file.name}</strong>
                  <span className="muted">{formatByteSize(item.file.size)}</span>
                </div>
                <div className="upload-item-status">
                  <span className={`status-badge status-badge--${item.status}`}>
                    {item.status === "queued" && "Queued"}
                    {item.status === "uploading" && "Uploading"}
                    {item.status === "uploaded" && "Uploaded"}
                    {item.status === "error" && "Error"}
                  </span>
                  {item.errorMessage ? (
                    <span className="error-message">{item.errorMessage}</span>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="button-link"
                  onClick={() => handleRemoveUpload(item.id)}
                  disabled={item.status === "uploading"}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : null}

        <details
          className="advanced-options"
          open={advancedOpen}
          onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
        >
          <summary>Advanced options</summary>
          <div className="advanced-panel">
            <div className="form-field">
              <label className="form-label" htmlFor="metadata-json">
                Metadata (JSON)
              </label>
              <textarea
                id="metadata-json"
                className="form-textarea"
                rows={6}
                value={metadataInput}
                onChange={(event) => setMetadataInput(event.target.value)}
              />
            </div>
            <div className="form-grid">
              <div className="form-field">
                <label className="form-label" htmlFor="expires-at">
                  Expiry date
                </label>
                <input
                  id="expires-at"
                  type="date"
                  className="form-input"
                  value={expiryDate}
                  onChange={(event) => setExpiryDate(event.target.value)}
                />
              </div>
              <div className="form-field">
                <span className="form-label">Target configurations</span>
                {matchingConfigurations.length === 0 ? (
                  <p className="muted">No configurations available for this document type.</p>
                ) : (
                  <div className="checkbox-list">
                    {matchingConfigurations.map((configuration) => {
                      const id = configuration.configuration_id;
                      const checked = selectedConfigurationIds.includes(id);
                      return (
                        <label key={id} className="checkbox-option">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => {
                              const isChecked = event.target.checked;
                              setSelectedConfigurationIds((current) => {
                                if (isChecked) {
                                  return Array.from(new Set([...current, id]));
                                }
                                return current.filter((value) => value !== id);
                              });
                            }}
                          />
                          <span>{describeConfiguration(configuration)}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </details>

        <div className="actions">
          <button
            type="button"
            className="button-primary"
            onClick={handleUploadAll}
            disabled={isUploadDisabled}
          >
            {isUploading ? "Uploading…" : "Upload files"}
          </button>
        </div>
      </section>

      <section className="section">
        <header className="section-header">
          <h2>Workspace documents</h2>
          {isDocumentsFetching ? <span className="muted">Refreshing…</span> : null}
        </header>
        {isDocumentsLoading ? (
          <div className="placeholder-card">Loading documents…</div>
        ) : workspaceDocuments.length === 0 ? (
          <div className="placeholder-card">
            <p>No documents uploaded yet. Use the uploader above to ingest your first files.</p>
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Filename</th>
                  <th scope="col">Size</th>
                  <th scope="col">Uploaded</th>
                  <th scope="col">Expires</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="column-actions">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {workspaceDocuments.map((document) => (
                  <tr key={document.id}>
                    <th scope="row">
                      <div className="cell-main">
                        <span>{document.filename}</span>
                        {document.documentType ? (
                          <span className="muted">{document.documentType}</span>
                        ) : null}
                      </div>
                    </th>
                    <td>{formatByteSize(document.byteSize)}</td>
                    <td>{formatDateTime(document.createdAt)}</td>
                    <td>{formatDateTime(document.expiresAt)}</td>
                    <td>
                      <span
                        className={`status-badge status-badge--${document.status}`}
                      >
                        {formatDocumentStatus(document.status)}
                      </span>
                    </td>
                    <td className="column-actions">
                      <div className="action-group">
                        <a
                          href={
                            resolvedWorkspaceId
                              ? buildDocumentDownloadUrl(
                                  resolvedWorkspaceId,
                                  document.id,
                                )
                              : "#"
                          }
                          className="button-link"
                        >
                          Download
                        </a>
                        <button
                          type="button"
                          className="button-link"
                          onClick={() => setMetadataDocumentId(document.id)}
                        >
                          Metadata
                        </button>
                        <button
                          type="button"
                          className="button-link"
                          onClick={() => handleDeleteDocument(document.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {activeDocument ? (
        <div className="modal" role="dialog" aria-modal="true">
          <div className="modal-backdrop" onClick={() => setMetadataDocumentId(null)} />
          <div className="modal-content">
            <header className="modal-header">
              <h3>Metadata for {activeDocument.filename}</h3>
              <button
                type="button"
                className="button-link"
                onClick={() => setMetadataDocumentId(null)}
              >
                Close
              </button>
            </header>
            <div className="modal-body">
              <dl className="metadata-list">
                <div>
                  <dt>Document type</dt>
                  <dd>{activeDocument.documentType ?? "—"}</dd>
                </div>
                <div>
                  <dt>Stored URI</dt>
                  <dd>{activeDocument.storedUri}</dd>
                </div>
                <div>
                  <dt>SHA-256</dt>
                  <dd>{activeDocument.sha256}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{formatDocumentStatus(activeDocument.status)}</dd>
                </div>
                {activeDocument.deletedAt ? (
                  <div>
                    <dt>Deleted at</dt>
                    <dd>{formatDateTime(activeDocument.deletedAt)}</dd>
                  </div>
                ) : null}
                {activeDocument.deleteReason ? (
                  <div>
                    <dt>Delete reason</dt>
                    <dd>{activeDocument.deleteReason}</dd>
                  </div>
                ) : null}
              </dl>
              <pre className="metadata-json">
                {JSON.stringify(activeDocument.metadata, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
