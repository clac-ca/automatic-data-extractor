import type { DocumentChangeNotification } from "@/api/documents";

export function partitionDocumentChanges(changes: readonly DocumentChangeNotification[]) {
  const opById = new Map<string, DocumentChangeNotification["op"]>();
  changes.forEach((change) => {
    if (change.documentId && change.op) {
      opById.set(change.documentId, change.op);
    }
  });

  const deleteIds: string[] = [];
  const upsertIds: string[] = [];
  opById.forEach((op, documentId) => {
    if (op === "delete") {
      deleteIds.push(documentId);
      return;
    }
    upsertIds.push(documentId);
  });

  return { deleteIds, upsertIds };
}
