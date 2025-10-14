import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "../../../shared/lib/storage";
import { DocumentDrawer } from "./DocumentDrawer";
import type { DocumentDrawerDocument } from "./DocumentDrawer";
import { useWorkspaceDocumentsQuery } from "../hooks/useWorkspaceDocumentsQuery";

export interface WorkspaceDocumentRailProps {
  readonly workspaceId: string;
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
  readonly onSelectDocument: (documentId: string) => void;
  readonly onCreateDocument?: () => void;
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
}: WorkspaceDocumentRailProps) {
  const pinsStorage = useMemo(
    () => createScopedStorage(`ade.workspace.${workspaceId}.document_pins`),
    [workspaceId],
  );
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => pinsStorage.get<string[]>() ?? []);

  useEffect(() => {
    setPinnedIds(pinsStorage.get<string[]>() ?? []);
  }, [pinsStorage, workspaceId]);

  useEffect(() => {
    pinsStorage.set(pinnedIds);
  }, [pinsStorage, pinnedIds]);

  const documentsQuery = useWorkspaceDocumentsQuery(workspaceId);
  const documents = documentsQuery.data ?? [];

  const drawerDocuments = useMemo<DocumentDrawerDocument[]>(() => {
    return documents.map((document) => {
      const metadata = document.metadata as { pinned?: unknown };
      const pinnedFromMetadata = metadata?.pinned === true;
      const pinned = pinnedFromMetadata || pinnedIds.includes(document.id);
      return {
        id: document.id,
        name: document.name,
        updatedAtLabel: formatUpdatedAt(document.updatedAt),
        pinned,
      } satisfies DocumentDrawerDocument;
    });
  }, [documents, pinnedIds]);

  const handleTogglePin = useCallback(
    (documentId: string, nextPinned: boolean) => {
      setPinnedIds((current) => {
        const set = new Set(current);
        if (nextPinned) {
          set.add(documentId);
        } else {
          set.delete(documentId);
        }
        return Array.from(set);
      });
    },
    [],
  );

  return (
    <DocumentDrawer
      documents={drawerDocuments}
      collapsed={collapsed}
      onToggleCollapse={onToggleCollapse}
      onSelectDocument={onSelectDocument}
      onCreateDocument={onCreateDocument}
      onTogglePin={handleTogglePin}
      isLoading={documentsQuery.isLoading}
      isError={documentsQuery.isError}
      onRetry={documentsQuery.refetch}
    />
  );
}
