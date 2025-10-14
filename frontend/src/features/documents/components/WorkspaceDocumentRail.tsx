import { useMemo } from "react";

import { DocumentDrawer } from "./DocumentDrawer";
import type { DocumentDrawerDocument } from "./DocumentDrawer";
import { useWorkspaceDocumentsQuery } from "../hooks/useWorkspaceDocumentsQuery";

export interface WorkspaceDocumentRailProps {
  readonly workspaceId: string;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onSelectDocument: (documentId: string) => void;
  readonly onCreateDocument?: () => void;
  readonly pinnedDocumentIds: readonly string[];
  readonly onTogglePin: (documentId: string, nextPinned: boolean) => void;
}

function formatUpdatedAt(timestamp: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(timestamp));
  } catch (error) {
    console.warn("Failed to format timestamp", error);
    return timestamp;
  }
}

export function WorkspaceDocumentRail({
  workspaceId,
  collapsed,
  onToggleCollapse,
  onSelectDocument,
  onCreateDocument,
  pinnedDocumentIds,
  onTogglePin,
}: WorkspaceDocumentRailProps) {
  const documentsQuery = useWorkspaceDocumentsQuery(workspaceId);
  const documents = documentsQuery.data ?? [];

  const drawerDocuments = useMemo<DocumentDrawerDocument[]>(() => {
    return documents.map((document) => {
      const metadata = document.metadata as { pinned?: unknown };
      const pinnedFromMetadata = metadata?.pinned === true;
      const pinned = pinnedFromMetadata || pinnedDocumentIds.includes(document.id);
      return {
        id: document.id,
        name: document.name,
        updatedAtLabel: formatUpdatedAt(document.updatedAt),
        pinned,
      } satisfies DocumentDrawerDocument;
    });
  }, [documents, pinnedDocumentIds]);

  return (
    <DocumentDrawer
      documents={drawerDocuments}
      collapsed={collapsed}
      onToggleCollapse={onToggleCollapse}
      onSelectDocument={onSelectDocument}
      onCreateDocument={onCreateDocument}
      onTogglePin={onTogglePin}
      isLoading={documentsQuery.isLoading}
      isError={documentsQuery.isError}
      onRetry={documentsQuery.refetch}
    />
  );
}
