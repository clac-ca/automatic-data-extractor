import { get } from "../../shared/api/client";
import type { DocumentRecord, WorkspaceDocumentSummary } from "../../shared/types/documents";

function normaliseDocument(record: DocumentRecord): WorkspaceDocumentSummary {
  return {
    id: record.document_id,
    name: record.original_filename,
    updatedAt: record.updated_at,
    createdAt: record.created_at,
    byteSize: record.byte_size,
    contentType: record.content_type,
    metadata: record.metadata ?? {},
  };
}

export async function fetchWorkspaceDocuments(workspaceId: string, signal?: AbortSignal) {
  const response = await get<DocumentRecord[]>(`/workspaces/${workspaceId}/documents`, { signal });
  return response.map((record) => normaliseDocument(record));
}
