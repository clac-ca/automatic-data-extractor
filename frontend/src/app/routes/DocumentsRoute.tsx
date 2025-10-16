import { useEffect, useMemo } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { useWorkspaceDocumentsQuery } from "../../features/documents/hooks/useWorkspaceDocumentsQuery";
import type { WorkspaceDocumentSummary } from "../../shared/types/documents";
import { PageState } from "../components/PageState";
import { Button } from "../../ui";
import { useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { trackEvent } from "../../shared/telemetry/events";

export function DocumentsRoute() {
  const { workspace } = useWorkspaceContext();
  const documentsQuery = useWorkspaceDocumentsQuery(workspace.id);
  const [searchParams, setSearchParams] = useSearchParams();
  const { openInspector, closeInspector } = useWorkspaceChrome();

  const rawView = searchParams.get("view") ?? "";
  const viewMode: "all" | "recent" | "pinned" | "archived" | "new" =
    rawView === "recent"
      ? "recent"
      : rawView === "pinned"
        ? "pinned"
        : rawView === "archived"
          ? "archived"
          : rawView === "new"
            ? "new"
            : "all";
  const selectedDocumentId = searchParams.get("document");

  const documents = useMemo(() => {
    const list = documentsQuery.data ?? [];
    switch (viewMode) {
      case "recent":
        return [...list]
          .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
          .slice(0, 20);
      case "pinned":
        return list.filter((document) => {
          const metadata = document.metadata ?? {};
          return metadata.pinned === true;
        });
      case "archived":
        return list.filter((document) => {
          const metadata = document.metadata ?? {};
          return metadata.archived === true;
        });
      case "new":
      case "all":
      default:
        return list;
    }
  }, [documentsQuery.data, viewMode]);

  useEffect(() => {
    if (!selectedDocumentId) {
      closeInspector();
      return;
    }
    const match = documentsQuery.data?.find((document) => document.id === selectedDocumentId);
    if (!match) {
      if (!documentsQuery.isLoading && !documentsQuery.isFetching) {
        clearSelection(setSearchParams);
      }
      return;
    }
    const handleCleanup = () => clearSelection(setSearchParams);
    openInspector({
      title: match.name,
      content: <DocumentInspector document={match} />,
      onClose: handleCleanup,
    });
  }, [
    closeInspector,
    documentsQuery.data,
    documentsQuery.isFetching,
    documentsQuery.isLoading,
    openInspector,
    selectedDocumentId,
    setSearchParams,
  ]);

  if (documentsQuery.isLoading) {
    return <PageState title="Loading documents" variant="loading" />;
  }

  if (documentsQuery.isError) {
    return (
      <PageState
        title="Unable to load documents"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => documentsQuery.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  if (documents.length === 0) {
    const emptyTitle =
      viewMode === "pinned"
        ? "No pinned documents"
        : viewMode === "archived"
          ? "No archived documents"
          : "No documents yet";
    const emptyDescription =
      viewMode === "pinned"
        ? "Pin a document from the detail panel and it will appear here."
        : viewMode === "archived"
          ? "Archived documents will land here for long-term reference."
          : "Upload your first spreadsheet or PDF to kick off an extraction run.";
    return (
      <PageState
        title={emptyTitle}
        description={emptyDescription}
        variant="empty"
        action={
          viewMode === "archived" ? null : (
            <Button variant="primary" disabled>
              Upload coming soon
            </Button>
          )
        }
      />
    );
  }

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 id="page-title" className="text-2xl font-semibold text-slate-900">
            {viewMode === "pinned"
              ? "Pinned documents"
              : viewMode === "archived"
                ? "Archived documents"
                : "Documents"}
          </h1>
          <p className="text-sm text-slate-500">
            {viewMode === "pinned"
              ? "Your pinned uploads stay here for quick reference."
              : viewMode === "archived"
                ? "Archived uploads are kept for longer-term reference and cannot be edited."
                : "Manage uploaded files, review extraction status, and open item details without leaving the grid."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ViewSwitch viewMode={viewMode} onChange={(mode) => updateViewMode(mode, setSearchParams)} />
          <Button variant="primary" disabled>
            Upload document
          </Button>
        </div>
      </header>

      {viewMode === "new" ? (
        <div className="rounded-2xl border border-dashed border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-700">
          <p className="font-semibold">Upload flow coming soon</p>
          <p className="mt-1 text-brand-600">
            We&apos;re wiring the document upload dialog right now. In the meantime, drop files into the workspace inbox or use the CLI uploader.
          </p>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3">
                Name
              </th>
              <th scope="col" className="px-4 py-3">
                Type
              </th>
              <th scope="col" className="px-4 py-3">
                Size
              </th>
              <th scope="col" className="px-4 py-3">
                Last updated
              </th>
              <th scope="col" className="px-4 py-3 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {documents.map((document) => {
              const isActive = selectedDocumentId === document.id;
              return (
                <tr
                  key={document.id}
                  className={`hover:bg-slate-50 focus-within:bg-slate-50 ${isActive ? "bg-brand-50/40" : ""}`}
                >
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      className="text-sm font-semibold text-slate-800 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                    onClick={() => {
                      trackEvent({
                        name: "documents.inspect",
                        payload: { workspaceId: workspace.id, documentId: document.id },
                      });
                      setSearchParams((params) => {
                        params.set("document", document.id);
                        return params;
                      });
                    }}
                    >
                      {document.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {document.contentType ?? "Unknown"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{formatFileSize(document.byteSize)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatTimestamp(document.updatedAt)}</td>
                  <td className="px-4 py-3 text-right text-slate-500">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        trackEvent({
                          name: "documents.inspect",
                          payload: { workspaceId: workspace.id, documentId: document.id },
                        });
                        setSearchParams((params) => {
                          params.set("document", document.id);
                          return params;
                        });
                      }}
                    >
                      Review
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / Math.pow(1024, index);
  return `${size.toFixed(1)} ${units[index]}`;
}

function formatTimestamp(timestamp: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(timestamp));
  } catch {
    return timestamp;
  }
}

function ViewSwitch({
  viewMode,
  onChange,
}: {
  readonly viewMode: "all" | "recent" | "pinned" | "archived" | "new";
  readonly onChange: (view: "all" | "recent" | "pinned" | "archived") => void;
}) {
  const options: Array<{ mode: "all" | "recent" | "pinned" | "archived"; label: string }>
    = [
      { mode: "all", label: "All" },
      { mode: "recent", label: "Recent" },
      { mode: "pinned", label: "Pinned" },
      { mode: "archived", label: "Archived" },
    ];
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1 text-xs font-semibold text-slate-600">
      {options.map((option) => (
        <button
          key={option.mode}
          type="button"
          onClick={() => onChange(option.mode)}
          className={`rounded-md px-3 py-1 transition ${
            viewMode === option.mode
              ? "bg-brand-600 text-white shadow-sm"
              : "hover:bg-slate-100"
          }`}
          aria-pressed={viewMode === option.mode}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function updateViewMode(
  mode: "all" | "recent" | "pinned" | "archived",
  setSearchParams: ReturnType<typeof useSearchParams>[1],
) {
  setSearchParams((params) => {
    params.set("view", mode);
    params.delete("document");
    return params;
  });
}

function clearSelection(setSearchParams: ReturnType<typeof useSearchParams>[1]) {
  setSearchParams((params) => {
    params.delete("document");
    return params;
  });
}

function DocumentInspector({
  document,
}: {
  readonly document: WorkspaceDocumentSummary;
}) {
  const { closeInspector } = useWorkspaceChrome();

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h3 className="text-lg font-semibold text-slate-900">{document.name}</h3>
        <p className="text-sm text-slate-500">Content type: {document.contentType ?? "Unknown"}</p>
      </header>
      <section className="space-y-2 text-sm text-slate-600">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metadata</h4>
        <dl className="divide-y divide-slate-200 rounded-lg border border-slate-200">
          <InspectorField label="Size">{formatFileSize(document.byteSize)}</InspectorField>
          <InspectorField label="Created">{formatTimestamp(document.createdAt)}</InspectorField>
          <InspectorField label="Updated">{formatTimestamp(document.updatedAt)}</InspectorField>
        </dl>
      </section>
      <section className="space-y-2 text-sm text-slate-600">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Raw metadata</h4>
        <pre className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-900/90 p-3 text-xs text-slate-100">
          {JSON.stringify(document.metadata, null, 2)}
        </pre>
      </section>
      <div className="flex justify-end">
        <Button variant="secondary" onClick={closeInspector}>
          Close
        </Button>
      </div>
    </div>
  );
}

function InspectorField({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-600">{children}</dd>
    </div>
  );
}
