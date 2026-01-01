import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaceDocuments } from "@api/documents";
import { documentChangesStreamUrl, streamDocumentChanges } from "@api/documents/changes";
import { ApiError } from "@api/errors";
import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { PageState } from "@components/layouts/page-state";
import { Button } from "@components/ui/button";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { useNavigate } from "@app/navigation/history";
import { readPreferredWorkspaceId } from "@lib/workspacePreferences";
import { TablecnDocumentsTable } from "./components/TablecnDocumentsTable";
import { TablecnPlaygroundLayout } from "./components/TablecnPlaygroundLayout";
import { useDocumentsListParams } from "./hooks/useDocumentsListParams";
import type { DocumentChangeEntry, DocumentListResponse } from "./types";
import { normalizeDocumentsFilters, normalizeDocumentsSort } from "./utils";

export default function TablecnPlaygroundScreen() {
  return (
    <RequireSession>
      <TablecnDocumentsPlayground />
    </RequireSession>
  );
}

type MergeChangeResult = {
  data: DocumentListResponse;
  updatesAvailable: boolean;
};

function mergeDocumentChange(
  existing: DocumentListResponse,
  change: DocumentChangeEntry,
): MergeChangeResult {
  const id = change.documentId ?? change.row?.id;
  if (!id) {
    return {
      data: existing,
      updatesAvailable: Boolean(change.requiresRefresh),
    };
  }

  const items = existing.items ?? [];
  const index = items.findIndex((item) => item.id === id);
  let updatesAvailable = Boolean(change.requiresRefresh);
  if (index === -1) {
    if (change.type === "document.upsert" && change.row && change.matchesFilters) {
      updatesAvailable = true;
    }
    return { data: existing, updatesAvailable };
  }

  if (change.type === "document.deleted") {
    return {
      data: { ...existing, items: items.filter((item) => item.id !== id) },
      updatesAvailable,
    };
  }

  if (change.type === "document.upsert" && change.row) {
    if (change.matchesFilters === false) {
      updatesAvailable = true;
      return {
        data: { ...existing, items: items.filter((item) => item.id !== id) },
        updatesAvailable,
      };
    }

    const nextItems = items.slice();
    nextItems[index] = change.row;
    if (change.matchesFilters !== true) {
      updatesAvailable = true;
    }
    return { data: { ...existing, items: nextItems }, updatesAvailable };
  }

  return { data: existing, updatesAvailable };
}

function sleep(duration: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    let timeout: number;
    const onAbort = () => {
      window.clearTimeout(timeout);
      signal.removeEventListener("abort", onAbort);
      resolve();
    };
    timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, duration);
    signal.addEventListener("abort", onAbort);
  });
}

function TablecnDocumentsPlayground() {
  const session = useSession();
  const navigate = useNavigate();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data?.items],
  );

  const preferredIds = useMemo(
    () =>
      [readPreferredWorkspaceId(), session.user.preferred_workspace_id].filter(
        (value): value is string => Boolean(value),
      ),
    [session.user.preferred_workspace_id],
  );

  const preferredWorkspace = useMemo(
    () =>
      preferredIds
        .map((id) => workspaces.find((workspace) => workspace.id === id))
        .find((match) => Boolean(match)),
    [preferredIds, workspaces],
  );

  const workspace = preferredWorkspace ?? workspaces[0] ?? null;

  if (workspacesQuery.isLoading) {
    return <PageState title="Loading documents" variant="loading" />;
  }

  if (workspacesQuery.isError) {
    return (
      <PageState
        title="Unable to load workspaces"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => workspacesQuery.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  if (!workspace) {
    return (
      <PageState
        title="No workspaces yet"
        description="Create a workspace to view documents."
        variant="empty"
        action={
          <Button variant="secondary" onClick={() => navigate("/workspaces")}>
            Go to workspaces
          </Button>
        }
      />
    );
  }

  return <TablecnDocumentsContainer workspaceId={workspace.id} />;
}

function TablecnDocumentsContainer({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const [updatesAvailable, setUpdatesAvailable] = useState(false);
  const lastCursorRef = useRef<string | null>(null);

  const { page, perPage, sort, filters, joinOperator, q } =
    useDocumentsListParams();
  const normalizedSort = useMemo(() => normalizeDocumentsSort(sort), [sort]);
  const normalizedFilters = useMemo(
    () => normalizeDocumentsFilters(filters),
    [filters],
  );
  const queryKey = useMemo(
    () => [
      "tablecn-documents",
      workspaceId,
      page,
      perPage,
      sort,
      filters,
      joinOperator,
      q,
    ],
    [workspaceId, page, perPage, sort, filters, joinOperator, q],
  );
  const documentsQuery = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          page,
          perPage,
          sort: normalizedSort,
          filters: normalizedFilters.length > 0 ? normalizedFilters : undefined,
          joinOperator: joinOperator ?? undefined,
          q: q ?? undefined,
        },
        signal,
      ),
    enabled: Boolean(workspaceId),
  });
  const { refetch: refetchDocuments } = documentsQuery;
  const changesCursor =
    documentsQuery.data?.changesCursor ?? documentsQuery.data?.changesCursorHeader ?? null;

  const applyChange = useCallback(
    (change: DocumentChangeEntry) => {
      let shouldPrompt = Boolean(change.requiresRefresh);

      queryClient.setQueryData<DocumentListResponse>(queryKey, (existing) => {
        if (!existing) {
          return existing;
        }
        const result = mergeDocumentChange(existing, change);
        shouldPrompt = shouldPrompt || result.updatesAvailable;
        return result.data;
      });

      if (shouldPrompt) {
        setUpdatesAvailable((current) => current || shouldPrompt);
      }
    },
    [queryClient, queryKey],
  );

  useEffect(() => {
    setUpdatesAvailable(false);
    lastCursorRef.current = changesCursor;
  }, [changesCursor, filters, joinOperator, page, perPage, q, sort, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !changesCursor) return;

    const controller = new AbortController();
    let retryAttempt = 0;

    const streamChanges = async () => {
      while (!controller.signal.aborted) {
        const cursor = lastCursorRef.current ?? changesCursor;
        const streamUrl = documentChangesStreamUrl(workspaceId, {
          cursor,
          sort: normalizedSort ?? undefined,
          filters: normalizedFilters.length > 0 ? normalizedFilters : undefined,
          joinOperator: joinOperator ?? undefined,
          q: q ?? undefined,
        });

        try {
          for await (const change of streamDocumentChanges(streamUrl, controller.signal)) {
            lastCursorRef.current = change.cursor;
            applyChange(change);
            retryAttempt = 0;
          }
        } catch (error) {
          if (controller.signal.aborted) return;

          if (error instanceof ApiError && error.status === 410) {
            setUpdatesAvailable(false);
            void refetchDocuments();
            return;
          }

          console.warn("Tablecn document change stream failed", error);
        }

        if (controller.signal.aborted) return;

        const baseDelay = 1000;
        const maxDelay = 30000;
        const delay = Math.min(maxDelay, baseDelay * 2 ** Math.min(retryAttempt, 5));
        retryAttempt += 1;
        const jitter = Math.floor(delay * 0.15 * Math.random());
        await sleep(delay + jitter, controller.signal);
      }
    };

    void streamChanges();

    return () => controller.abort();
  }, [
    applyChange,
    changesCursor,
    joinOperator,
    normalizedFilters,
    normalizedSort,
    q,
    refetchDocuments,
    workspaceId,
  ]);

  if (documentsQuery.isLoading) {
    return <PageState title="Loading documents" variant="loading" />;
  }

  if (documentsQuery.isError) {
    return (
      <PageState
        title="Unable to load documents"
        description="Refresh the page or try again later."
        variant="error"
        action={
          <Button variant="secondary" onClick={() => documentsQuery.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  const pageCount = documentsQuery.data?.pageCount ?? 1;
  const handleRefresh = () => {
    setUpdatesAvailable(false);
    void refetchDocuments();
  };

  return (
    <TablecnPlaygroundLayout>
      {updatesAvailable ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-sm">
          <div>
            <p className="font-semibold text-foreground">Updates available</p>
            <p className="text-muted-foreground">
              Refresh to load the latest changes.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefresh}
              isLoading={documentsQuery.isFetching}
            >
              Refresh
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setUpdatesAvailable(false)}>
              Dismiss
            </Button>
          </div>
        </div>
      ) : null}
      <TablecnDocumentsTable
        data={documentsQuery.data?.items ?? []}
        pageCount={pageCount}
      />
    </TablecnPlaygroundLayout>
  );
}
