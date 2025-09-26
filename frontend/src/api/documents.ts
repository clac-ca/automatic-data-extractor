import { ApiClient } from "@api/client";

export interface DocumentRecord {
  readonly documentId: string;
  readonly originalFilename: string;
  readonly contentType: string | null;
  readonly byteSize: number;
  readonly sha256: string;
  readonly storedUri: string;
  readonly metadata: Record<string, unknown>;
  readonly expiresAt: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly deletedAt: string | null;
  readonly deletedBy: string | null;
  readonly deleteReason: string | null;
}

interface DocumentRecordResponse {
  readonly document_id: string;
  readonly original_filename: string;
  readonly content_type: string | null;
  readonly byte_size: number;
  readonly sha256: string;
  readonly stored_uri: string;
  readonly metadata: Record<string, unknown>;
  readonly expires_at: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly deleted_at: string | null;
  readonly deleted_by: string | null;
  readonly delete_reason: string | null;
}

export interface ListDocumentsParams {
  readonly limit?: number;
  readonly offset?: number;
}

export async function listDocuments(
  client: ApiClient,
  workspaceId: string,
  params: ListDocumentsParams = {}
): Promise<DocumentRecord[]> {
  const response = await client.get<DocumentRecordResponse[]>(
    `/workspaces/${workspaceId}/documents`,
    {
      query: {
        limit: params.limit,
        offset: params.offset
      }
    }
  );

  return response.map(transformDocument);
}

function transformDocument(record: DocumentRecordResponse): DocumentRecord {
  return {
    documentId: record.document_id,
    originalFilename: record.original_filename,
    contentType: record.content_type,
    byteSize: record.byte_size,
    sha256: record.sha256,
    storedUri: record.stored_uri,
    metadata: record.metadata,
    expiresAt: record.expires_at,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    deletedAt: record.deleted_at,
    deletedBy: record.deleted_by,
    deleteReason: record.delete_reason
  };
}
