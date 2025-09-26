import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";

import {
  buildDocumentDownloadUrl,
  deleteWorkspaceDocument,
  fetchWorkspaceDocuments,
  normaliseDocument,
  type DocumentRecord,
  type WorkspaceDocument,
  uploadWorkspaceDocument,
  type DocumentUploadOptions,
} from "../../api/documents";
import {
  fetchActiveConfigurations,
  type ConfigurationRecord,
} from "../../api/configurations";
import {
  isUnauthorizedError,
  normaliseErrorMessage,
} from "../../api/errors";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../../components/ToastProvider";

function documentsQueryKey(workspaceId: string | null, documentType: string | null) {
  if (!workspaceId) {
    return ["documents"] as const;
  }
  return ["workspaces", workspaceId, "documents", documentType ?? "all"] as const;
}

function configurationsQueryKey(workspaceId: string | null) {
  if (!workspaceId) {
    return ["configurations", "active"] as const;
  }
  return ["workspaces", workspaceId, "configurations", "active"] as const;
}

export function useWorkspaceDocumentsQuery(
  workspaceId: string | null,
  documentType: string | null,
) {
  const auth = useAuth();
  const { pushToast } = useToast();
  const lastError = useRef<unknown>(null);

  const queryKey = useMemo(
    () => documentsQueryKey(workspaceId, documentType),
    [workspaceId, documentType],
  );

  const query = useQuery({
    queryKey,
    enabled:
      Boolean(workspaceId) && auth.status === "authenticated" && Boolean(auth.token),
    queryFn: async () => {
      if (!workspaceId) {
        throw new Error("Workspace identifier is required");
      }
      if (!auth.token) {
        throw new Error("Authentication required");
      }
      const records = await fetchWorkspaceDocuments(auth.token, workspaceId);
      const documents = records.map(normaliseDocument);
      if (!documentType) {
        return documents;
      }
      return documents.filter((item) => item.documentType === documentType);
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const { error } = query;

  useEffect(() => {
    if (!error) {
      lastError.current = null;
      return;
    }
    if (lastError.current === error) {
      return;
    }
    lastError.current = error;
    if (isUnauthorizedError(error)) {
      pushToast({
        tone: "error",
        title: "Session expired",
        description: "Please sign in again to continue.",
      });
      auth.signOut();
      return;
    }
    pushToast({
      tone: "error",
      title: "Document error",
      description: normaliseErrorMessage(error),
    });
  }, [auth, error, pushToast]);

  return query;
}

export function useActiveConfigurationsQuery(workspaceId: string | null) {
  const auth = useAuth();
  const { pushToast } = useToast();
  const lastError = useRef<unknown>(null);

  const queryKey = useMemo(
    () => configurationsQueryKey(workspaceId),
    [workspaceId],
  );

  const query = useQuery({
    queryKey,
    enabled:
      Boolean(workspaceId) && auth.status === "authenticated" && Boolean(auth.token),
    queryFn: async (): Promise<ConfigurationRecord[]> => {
      if (!workspaceId) {
        throw new Error("Workspace identifier is required");
      }
      if (!auth.token) {
        throw new Error("Authentication required");
      }
      return fetchActiveConfigurations(auth.token, workspaceId);
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const { error } = query;

  useEffect(() => {
    if (!error) {
      lastError.current = null;
      return;
    }
    if (lastError.current === error) {
      return;
    }
    lastError.current = error;
    if (isUnauthorizedError(error)) {
      pushToast({
        tone: "error",
        title: "Session expired",
        description: "Please sign in again to continue.",
      });
      auth.signOut();
      return;
    }
    pushToast({
      tone: "error",
      title: "Configuration error",
      description: normaliseErrorMessage(error),
    });
  }, [auth, error, pushToast]);

  return query;
}

interface DeleteParams {
  workspaceId: string;
  documentId: string;
  reason?: string | null;
}

export function useDeleteDocumentMutation() {
  const auth = useAuth();
  const { pushToast } = useToast();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ workspaceId, documentId, reason }: DeleteParams) => {
      if (!auth.token) {
        throw new Error("Authentication required");
      }
      await deleteWorkspaceDocument(auth.token, workspaceId, documentId, {
        reason: reason ?? null,
      });
      return { workspaceId };
    },
    onSuccess: async ({ workspaceId }) => {
      pushToast({ tone: "success", title: "Document removed" });
      await queryClient.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "documents"],
        exact: false,
      });
    },
    onError: (error: unknown) => {
      if (isUnauthorizedError(error)) {
        pushToast({
          tone: "error",
          title: "Session expired",
          description: "Please sign in again to continue.",
        });
        auth.signOut();
        return;
      }
      pushToast({
        tone: "error",
        title: "Delete failed",
        description: normaliseErrorMessage(error),
      });
    },
  });
}

interface UploadParams {
  workspaceId: string;
  file: File;
  options: DocumentUploadOptions;
}

export function useUploadDocumentMutation() {
  const auth = useAuth();
  const { pushToast } = useToast();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ workspaceId, file, options }: UploadParams) => {
      if (!auth.token) {
        throw new Error("Authentication required");
      }
      const record = await uploadWorkspaceDocument(
        auth.token,
        workspaceId,
        file,
        options,
      );
      return { workspaceId, record };
    },
    onSuccess: async ({ workspaceId, record }) => {
      pushToast({
        tone: "success",
        title: `${record.original_filename} uploaded`,
      });
      await queryClient.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "documents"],
        exact: false,
      });
    },
    onError: (error: unknown) => {
      if (isUnauthorizedError(error)) {
        pushToast({
          tone: "error",
          title: "Session expired",
          description: "Please sign in again to continue.",
        });
        auth.signOut();
        return;
      }
      pushToast({
        tone: "error",
        title: "Upload failed",
        description: normaliseErrorMessage(error),
      });
    },
  });
}

export function useDocumentDownloadUrl(
  workspaceId: string | null,
  documentId: string,
) {
  return useMemo(() => {
    if (!workspaceId) {
      return null;
    }
    return buildDocumentDownloadUrl(workspaceId, documentId);
  }, [workspaceId, documentId]);
}

export type { DocumentRecord, WorkspaceDocument };
