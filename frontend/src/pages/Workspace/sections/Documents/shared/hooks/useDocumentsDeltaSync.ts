import { useCallback, useEffect, useRef } from "react";

import {
  fetchWorkspaceDocumentsDelta,
  type DocumentChangeNotification,
} from "@/api/documents";
import { ApiError } from "@/api/errors";
import { useWorkspaceDocumentsChanges } from "@/pages/Workspace/context/WorkspaceDocumentsStreamContext";

type UseDocumentsDeltaSyncOptions = {
  readonly workspaceId: string;
  readonly changesCursor: string | null;
  readonly resetKey?: string | number | null;
  readonly onApplyChanges: (
    changes: DocumentChangeNotification[],
  ) => Promise<void> | void;
  readonly onSnapshotStale?: () => void;
  readonly debounceMs?: number;
};

export function useDocumentsDeltaSync({
  workspaceId,
  changesCursor,
  resetKey,
  onApplyChanges,
  onSnapshotStale,
  debounceMs = 250,
}: UseDocumentsDeltaSyncOptions) {
  const deltaTokenRef = useRef<string | null>(null);
  const deltaPullInFlightRef = useRef(false);
  const deltaPullQueuedRef = useRef(false);
  const pendingNotifyRef = useRef(false);
  const debounceTimerRef = useRef<number | null>(null);

  useEffect(() => {
    deltaTokenRef.current = null;
    pendingNotifyRef.current = false;
  }, [workspaceId, resetKey]);

  useEffect(() => {
    if (changesCursor) {
      deltaTokenRef.current = changesCursor;
    }
  }, [changesCursor]);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current !== null) {
        window.clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
    };
  }, []);

  const pullDelta = useCallback(async () => {
    if (deltaPullInFlightRef.current) {
      deltaPullQueuedRef.current = true;
      return;
    }

    const since = deltaTokenRef.current;
    if (!since) {
      pendingNotifyRef.current = true;
      return;
    }

    deltaPullInFlightRef.current = true;
    deltaPullQueuedRef.current = false;
    try {
      let nextSince = since;
      const collected: DocumentChangeNotification[] = [];
      while (true) {
        const delta = await fetchWorkspaceDocumentsDelta(workspaceId, {
          since: nextSince,
        });
        collected.push(...(delta.changes ?? []));
        if (delta.nextSince) {
          nextSince = delta.nextSince;
        }
        if (!delta.hasMore) {
          break;
        }
      }

      deltaTokenRef.current = nextSince;
      if (collected.length > 0) {
        await onApplyChanges(collected);
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 410) {
        onSnapshotStale?.();
      }
    } finally {
      deltaPullInFlightRef.current = false;
      if (deltaPullQueuedRef.current) {
        deltaPullQueuedRef.current = false;
        void pullDelta();
      }
    }
  }, [onApplyChanges, onSnapshotStale, workspaceId]);

  const scheduleDeltaPull = useCallback(
    (change?: DocumentChangeNotification) => {
      if (!deltaTokenRef.current && change?.id) {
        deltaTokenRef.current = change.id;
        void onApplyChanges([change]);
        return;
      }

      pendingNotifyRef.current = true;
      if (debounceTimerRef.current !== null) {
        return;
      }

      debounceTimerRef.current = window.setTimeout(() => {
        debounceTimerRef.current = null;
        if (!pendingNotifyRef.current) {
          return;
        }
        pendingNotifyRef.current = false;
        void pullDelta();
      }, Math.max(0, debounceMs));
    },
    [debounceMs, onApplyChanges, pullDelta],
  );

  useEffect(() => {
    if (!changesCursor || !pendingNotifyRef.current) {
      return;
    }
    pendingNotifyRef.current = false;
    void pullDelta();
  }, [changesCursor, pullDelta]);

  useWorkspaceDocumentsChanges(
    useCallback(
      (change) => {
        scheduleDeltaPull(change);
      },
      [scheduleDeltaPull],
    ),
  );
}
