import { useCallback, useState } from "react";

import type { DocumentRow } from "../../shared/types";

export function useDocumentsBulkActions() {
  const [bulkAssignTargets, setBulkAssignTargets] = useState<DocumentRow[]>([]);
  const [bulkAssignChoice, setBulkAssignChoice] = useState<string>("");
  const [isBulkAssignSubmitting, setIsBulkAssignSubmitting] = useState(false);

  const [bulkTagTargets, setBulkTagTargets] = useState<DocumentRow[]>([]);
  const [bulkTagAdd, setBulkTagAdd] = useState<string[]>([]);
  const [bulkTagRemove, setBulkTagRemove] = useState<string[]>([]);
  const [isBulkTagSubmitting, setIsBulkTagSubmitting] = useState(false);

  const [bulkDeleteTargets, setBulkDeleteTargets] = useState<DocumentRow[]>([]);
  const [isBulkDeleteSubmitting, setIsBulkDeleteSubmitting] = useState(false);

  const [bulkRestoreTargets, setBulkRestoreTargets] = useState<DocumentRow[]>([]);
  const [isBulkRestoreSubmitting, setIsBulkRestoreSubmitting] = useState(false);

  const resetBulkActions = useCallback(() => {
    setBulkAssignTargets([]);
    setBulkAssignChoice("");
    setIsBulkAssignSubmitting(false);

    setBulkTagTargets([]);
    setBulkTagAdd([]);
    setBulkTagRemove([]);
    setIsBulkTagSubmitting(false);

    setBulkDeleteTargets([]);
    setIsBulkDeleteSubmitting(false);

    setBulkRestoreTargets([]);
    setIsBulkRestoreSubmitting(false);
  }, []);

  return {
    bulkAssignTargets,
    setBulkAssignTargets,
    bulkAssignChoice,
    setBulkAssignChoice,
    isBulkAssignSubmitting,
    setIsBulkAssignSubmitting,
    bulkTagTargets,
    setBulkTagTargets,
    bulkTagAdd,
    setBulkTagAdd,
    bulkTagRemove,
    setBulkTagRemove,
    isBulkTagSubmitting,
    setIsBulkTagSubmitting,
    bulkDeleteTargets,
    setBulkDeleteTargets,
    isBulkDeleteSubmitting,
    setIsBulkDeleteSubmitting,
    bulkRestoreTargets,
    setBulkRestoreTargets,
    isBulkRestoreSubmitting,
    setIsBulkRestoreSubmitting,
    resetBulkActions,
  };
}
