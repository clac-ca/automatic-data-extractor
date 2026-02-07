import type { DocumentActivityFilter } from "@/pages/Workspace/sections/Documents/shared/navigation";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentActivityComposer } from "./components/DocumentActivityComposer";
import { DocumentActivityFeed } from "./components/DocumentActivityFeed";
import { DocumentActivityHeader } from "./components/DocumentActivityHeader";
import { useDocumentActivityFeed } from "./hooks/useDocumentActivityFeed";

export function DocumentActivityTab({
  workspaceId,
  document,
  filter,
  onFilterChange,
}: {
  workspaceId: string;
  document: DocumentRow;
  filter: DocumentActivityFilter;
  onFilterChange: (filter: DocumentActivityFilter) => void;
}) {
  const model = useDocumentActivityFeed({
    workspaceId,
    document,
    filter,
  });

  return (
    <div className="flex h-full flex-col overflow-hidden bg-muted/20">
      <DocumentActivityHeader
        filter={filter}
        counts={model.counts}
        onFilterChange={onFilterChange}
      />

      <DocumentActivityFeed
        items={model.visibleItems}
        isLoading={model.isLoading}
        hasError={model.hasError}
        hasNextPage={model.hasNextPage}
        isFetchingNextPage={model.isFetchingNextPage}
        onLoadMore={model.fetchNextPage}
      />

      <DocumentActivityComposer
        workspaceId={workspaceId}
        currentUser={model.currentUser}
        isSubmitting={model.isSubmitting}
        submitError={model.submitError}
        onSubmit={model.submitComment}
      />
    </div>
  );
}
