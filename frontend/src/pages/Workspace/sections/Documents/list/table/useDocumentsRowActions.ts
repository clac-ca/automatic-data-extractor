import { useCallback, useState } from "react";

export type RowMutation = "delete" | "restore" | "assign" | "rename" | "tags" | "run";

export function useDocumentsRowActions() {
  const [pendingMutations, setPendingMutations] = useState<Record<string, Set<RowMutation>>>({});

  const markRowPending = useCallback((documentId: string, action: RowMutation) => {
    setPendingMutations((current) => {
      const next = new Set(current[documentId] ?? []);
      next.add(action);
      return { ...current, [documentId]: next };
    });
  }, []);

  const clearRowPending = useCallback((documentId: string, action?: RowMutation) => {
    setPendingMutations((current) => {
      const existing = current[documentId];
      if (!existing) return current;
      if (!action) {
        const next = { ...current };
        delete next[documentId];
        return next;
      }
      const nextSet = new Set(existing);
      nextSet.delete(action);
      if (nextSet.size === 0) {
        const next = { ...current };
        delete next[documentId];
        return next;
      }
      return { ...current, [documentId]: nextSet };
    });
  }, []);

  const isRowMutationPending = useCallback(
    (documentId: string) => (pendingMutations[documentId]?.size ?? 0) > 0,
    [pendingMutations],
  );

  const resetRowMutations = useCallback(() => {
    setPendingMutations({});
  }, []);

  return {
    pendingMutations,
    markRowPending,
    clearRowPending,
    isRowMutationPending,
    resetRowMutations,
  };
}
