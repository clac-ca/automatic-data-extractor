import { Button } from "../../../../ui";
import type { OwnerFilterValue, StatusFilterValue } from "../utils";

interface DocumentsEmptyStateProps {
  readonly owner: OwnerFilterValue;
  readonly status: StatusFilterValue;
  readonly hasDocuments: boolean;
  readonly onViewAll: () => void;
  readonly onClearStatus: () => void;
  readonly onUpload: () => void;
  readonly isUploading: boolean;
}

export function DocumentsEmptyState({
  owner,
  status,
  hasDocuments,
  onViewAll,
  onClearStatus,
  onUpload,
  isUploading,
}: DocumentsEmptyStateProps) {
  if (!hasDocuments) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <h2 className="text-lg font-semibold text-slate-800">Upload your first document</h2>
        <p className="max-w-md text-sm text-slate-500">
          Drag and drop a file anywhere in this panel or use the upload button to get started.
        </p>
        <Button onClick={onUpload} isLoading={isUploading}>
          Upload documents
        </Button>
      </div>
    );
  }

  const ownerDescription = owner === "mine" ? "your uploads" : "workspace uploads";
  const statusDescription = status === "all" ? "" : ` (${status})`;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">No documents match the current filters</h2>
        <p className="mt-2 max-w-md text-sm text-slate-500">
          Showing {ownerDescription}
          {statusDescription}. Adjust the filters or upload a new document.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        {owner === "mine" ? (
          <Button variant="secondary" onClick={onViewAll}>
            View all documents
          </Button>
        ) : null}
        {status !== "all" ? (
          <Button variant="secondary" onClick={onClearStatus}>
            Clear status filter
          </Button>
        ) : null}
        <Button onClick={onUpload} isLoading={isUploading}>
          Upload documents
        </Button>
      </div>
    </div>
  );
}
