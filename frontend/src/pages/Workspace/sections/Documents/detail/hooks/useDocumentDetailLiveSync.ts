import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useWorkspaceDocumentsChanges } from "@/pages/Workspace/context/WorkspaceDocumentsStreamContext";

export function useDocumentDetailLiveSync({
  workspaceId,
  documentId,
  enabled = true,
  debounceMs = 200,
}: {
  workspaceId: string;
  documentId: string;
  enabled?: boolean;
  debounceMs?: number;
}) {
  const queryClient = useQueryClient();
  const debounceTimerRef = useRef<number | null>(null);

  const invalidateDetailQueries = useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: ["documents-detail", workspaceId, documentId],
    });
    queryClient.invalidateQueries({
      queryKey: ["document-activity-runs", workspaceId, documentId],
    });
  }, [documentId, queryClient, workspaceId]);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current !== null) {
        window.clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
    };
  }, []);

  useWorkspaceDocumentsChanges(
    useCallback(
      (change) => {
        if (!enabled) return;
        if (change.documentId !== documentId) return;
        if (debounceTimerRef.current !== null) return;

        debounceTimerRef.current = window.setTimeout(() => {
          debounceTimerRef.current = null;
          invalidateDetailQueries();
        }, Math.max(0, debounceMs));
      },
      [debounceMs, documentId, enabled, invalidateDetailQueries],
    ),
  );
}
