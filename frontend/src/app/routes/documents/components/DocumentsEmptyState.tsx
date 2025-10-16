import { Button } from "../../../../ui";

interface DocumentsEmptyStateProps {
  readonly hasDocuments: boolean;
  readonly hasActiveFilters: boolean;
  readonly onClearFilters: () => void;
  readonly onUpload: () => void;
  readonly isUploading: boolean;
}

export function DocumentsEmptyState({
  hasDocuments,
  hasActiveFilters,
  onClearFilters,
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

  if (hasActiveFilters) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">No documents match the current filters</h2>
          <p className="mt-2 max-w-md text-sm text-slate-500">
            Adjust the filters or upload a new document to continue.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button variant="secondary" onClick={onClearFilters}>
            Clear filters
          </Button>
          <Button onClick={onUpload} isLoading={isUploading}>
            Upload documents
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <h2 className="text-lg font-semibold text-slate-800">No documents available</h2>
      <p className="max-w-md text-sm text-slate-500">
        There are no documents on this page yet. Upload a file to populate the workspace.
      </p>
      <Button onClick={onUpload} isLoading={isUploading}>
        Upload documents
      </Button>
    </div>
  );
}
