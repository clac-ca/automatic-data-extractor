import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaceDocuments, patchWorkspaceDocument, type DocumentPageResult } from "@api/documents";
import { documentChangesStreamUrl, streamDocumentChanges } from "@api/documents/changes";
import { patchDocumentTags, fetchTagCatalog } from "@api/documents/tags";
import { ApiError } from "@api/errors";
import { Link } from "@app/navigation/Link";
import { listWorkspaceMembers } from "@api/workspaces/api";
import { Button } from "@components/tablecn/ui/button";
import { useNotifications } from "@components/providers/notifications";
import { shortId } from "@pages/Workspace/sections/Documents/utils";
import { mergeDocumentChangeIntoPages } from "@pages/Workspace/sections/Documents/changeFeed";
import type { WorkspacePerson } from "@pages/Workspace/sections/Documents/types";

import { TablecnDocumentsTable } from "./TablecnDocumentsTable";
import { TablecnEmptyState, TablecnInlineBanner } from "./TablecnEmptyState";
import { useDocumentsListParams } from "../hooks/useDocumentsListParams";
import type { DocumentChangeEntry } from "../types";
import { normalizeDocumentsFilters, normalizeDocumentsSort } from "../utils";

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

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

export function TablecnDocumentsView({
  workspaceId,
  currentUser,
  configMissing = false,
  processingPaused = false,
  toolbarActions,
}: {
  workspaceId: string;
  currentUser: CurrentUser;
  configMissing?: boolean;
  processingPaused?: boolean;
  toolbarActions?: ReactNode;
}) {
  const queryClient = useQueryClient();
  const { notifyToast } = useNotifications();
  const [updatesAvailable, setUpdatesAvailable] = useState(false);
  const lastCursorRef = useRef<string | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  const { perPage, sort, filters, joinOperator, q } = useDocumentsListParams();
  const normalizedSort = useMemo(() => normalizeDocumentsSort(sort), [sort]);
  const normalizedFilters = useMemo(() => normalizeDocumentsFilters(filters), [filters]);
  const sortTokens = useMemo(
    () =>
      normalizedSort
        ? normalizedSort.split(",").map((token) => token.trim()).filter(Boolean)
        : [],
    [normalizedSort],
  );
  const filtersKey = useMemo(
    () => (normalizedFilters.length > 0 ? JSON.stringify(normalizedFilters) : ""),
    [normalizedFilters],
  );
  const queryKey = useMemo(
    () => [
      "tablecn-documents",
      workspaceId,
      perPage,
      normalizedSort,
      filtersKey,
      joinOperator,
      q,
    ],
    [workspaceId, perPage, normalizedSort, filtersKey, joinOperator, q],
  );

  const documentsQuery = useInfiniteQuery<DocumentPageResult>({
    queryKey,
    initialPageParam: 1,
    queryFn: ({ pageParam, signal }) =>
      fetchWorkspaceDocuments(
        workspaceId,
        {
          page: typeof pageParam === "number" ? pageParam : 1,
          perPage,
          sort: normalizedSort,
          filters: normalizedFilters.length > 0 ? normalizedFilters : undefined,
          joinOperator: joinOperator ?? undefined,
          q: q ?? undefined,
        },
        signal,
      ),
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pageCount ? lastPage.page + 1 : undefined,
    enabled: Boolean(workspaceId),
    staleTime: 15_000,
  });
  const {
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch: refetchDocuments,
  } = documentsQuery;

  const documents = useMemo(
    () => documentsQuery.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [documentsQuery.data?.pages],
  );
  const documentsById = useMemo(
    () => new Map(documents.map((doc) => [doc.id, doc])),
    [documents],
  );

  const membersQuery = useQuery({
    queryKey: ["tablecn-documents-members", workspaceId],
    queryFn: ({ signal }) =>
      listWorkspaceMembers(workspaceId, { page: 1, pageSize: 200, signal }),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const people = useMemo<WorkspacePerson[]>(() => {
    const set = new Map<string, WorkspacePerson>();
    const currentUserKey = `user:${currentUser.id}`;
    set.set(currentUserKey, {
      key: currentUserKey,
      label: currentUser.label,
      kind: "user",
      userId: currentUser.id,
    });

    const members = membersQuery.data?.items ?? [];
    members.forEach((member) => {
      const key = `user:${member.user_id}`;
      const label =
        member.user_id === currentUser.id
          ? currentUser.label
          : `Member ${shortId(member.user_id)}`;
      if (!set.has(key)) {
        set.set(key, { key, label, kind: "user", userId: member.user_id });
      }
    });

    return Array.from(set.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [currentUser.id, currentUser.label, membersQuery.data?.items]);

  const tagsQuery = useQuery({
    queryKey: ["tablecn-documents-tags", workspaceId],
    queryFn: ({ signal }) =>
      fetchTagCatalog(
        workspaceId,
        { page: 1, perPage: 200, sort: "-count" },
        signal,
      ),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });

  const tagOptions = useMemo(
    () => tagsQuery.data?.items?.map((item) => item.tag) ?? [],
    [tagsQuery.data?.items],
  );

  const updateDocumentRow = useCallback(
    (documentId: string, updates: Partial<DocumentPageResult["items"][number]>) => {
      queryClient.setQueryData(queryKey, (existing: typeof documentsQuery.data | undefined) => {
        if (!existing?.pages) return existing;
        return {
          ...existing,
          pages: existing.pages.map((page) => ({
            ...page,
            items: (page.items ?? []).map((item) =>
              item.id === documentId ? { ...item, ...updates } : item,
            ),
          })),
        };
      });
    },
    [queryClient, queryKey, documentsQuery.data],
  );

  const onAssign = useCallback(
    async (documentId: string, assigneeKey: string | null) => {
      const assigneeId = assigneeKey?.startsWith("user:") ? assigneeKey.slice(5) : null;
      const assigneeLabel = assigneeKey
        ? people.find((person) => person.key === assigneeKey)?.label ?? assigneeKey
        : null;
      const assigneeEmail = assigneeLabel && assigneeLabel.includes("@") ? assigneeLabel : "";

      try {
        const updated = await patchWorkspaceDocument(workspaceId, documentId, { assigneeId });
        updateDocumentRow(documentId, {
          assignee: updated.assignee ?? (assigneeId ? { id: assigneeId, name: assigneeLabel, email: assigneeEmail } : null),
        });
      } catch (error) {
        notifyToast({
          title: "Unable to update assignee",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      }
    },
    [notifyToast, people, updateDocumentRow, workspaceId],
  );

  const onToggleTag = useCallback(
    async (documentId: string, tag: string) => {
      const current = documentsById.get(documentId);
      if (!current) return;
      const tags = current.tags ?? [];
      const hasTag = tags.includes(tag);
      try {
        await patchDocumentTags(workspaceId, documentId, hasTag ? { remove: [tag] } : { add: [tag] });
        const nextTags = hasTag ? tags.filter((t) => t !== tag) : [...tags, tag];
        updateDocumentRow(documentId, { tags: nextTags });
      } catch (error) {
        notifyToast({
          title: "Unable to update tags",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      }
    },
    [documentsById, notifyToast, updateDocumentRow, workspaceId],
  );

  const changesCursor =
    documentsQuery.data?.pages[0]?.changesCursor ??
    documentsQuery.data?.pages[0]?.changesCursorHeader ??
    null;

  const applyChange = useCallback(
    (change: DocumentChangeEntry) => {
      const id = change.documentId ?? change.row?.id ?? null;
      const isVisible = id ? documentsById.has(id) : false;
      const canInsert =
        change.type === "document.upsert" &&
        Boolean(change.row) &&
        Boolean(change.matchesFilters) &&
        !change.requiresRefresh;
      const shouldPromptForNew =
        change.type === "document.upsert" &&
        Boolean(change.matchesFilters) &&
        !isVisible &&
        !canInsert;

      if (!isVisible && !canInsert) {
        if (change.requiresRefresh || shouldPromptForNew) {
          setUpdatesAvailable((current) => current || true);
        }
        return;
      }

      let shouldPrompt = Boolean(change.requiresRefresh);

      queryClient.setQueryData(queryKey, (existing: typeof documentsQuery.data | undefined) => {
        if (!existing) {
          return existing;
        }
        const result = mergeDocumentChangeIntoPages(existing, change, { sortTokens });
        shouldPrompt = shouldPrompt || result.updatesAvailable;
        return result.data;
      });

      if (shouldPrompt) {
        setUpdatesAvailable((current) => current || true);
      }
    },
    [documentsById, queryClient, queryKey, sortTokens],
  );

  useEffect(() => {
    setUpdatesAvailable(false);
    lastCursorRef.current = changesCursor;
  }, [changesCursor, filtersKey, joinOperator, perPage, q, normalizedSort, workspaceId]);

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

  useEffect(() => {
    if (!loadMoreRef.current) return;
    if (!hasNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        if (isFetchingNextPage) return;
        void fetchNextPage();
      },
      {
        root: scrollContainerRef.current,
        rootMargin: "200px",
      },
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  if (documentsQuery.isLoading) {
    return (
      <div className="min-h-[240px]">
        <TablecnEmptyState
          title="Loading documents"
          description="Fetching the latest processing activity."
        />
      </div>
    );
  }

  if (documentsQuery.isError) {
    return (
      <div className="min-h-[240px]">
        <TablecnEmptyState
          title="Unable to load documents"
          description="We could not refresh this view. Try again."
          action={{ label: "Try again", onClick: () => documentsQuery.refetch() }}
        />
      </div>
    );
  }

  const pageCount = documentsQuery.data?.pages[0]?.pageCount ?? 1;
  const handleRefresh = () => {
    setUpdatesAvailable(false);
    void documentsQuery.refetch();
  };

  const configBuilderPath = `/workspaces/${workspaceId}/config-builder`;
  const processingSettingsPath = `/workspaces/${workspaceId}/settings/processing`;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
      {configMissing ? (
        <TablecnInlineBanner
          title="No active configuration"
          description="Uploads will be stored, but runs won't start until you activate a configuration."
          className="border-warning-200 bg-warning-50/60 text-warning-900 dark:border-warning-500/40 dark:bg-warning-500/10 dark:text-warning-100"
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={configBuilderPath}>Open config builder</Link>
            </Button>
          }
        />
      ) : null}
      {processingPaused ? (
        <TablecnInlineBanner
          title="Processing paused"
          description="Uploads are queued and won't start until processing is resumed."
          className="border-warning-200 bg-warning-50/60 text-warning-900 dark:border-warning-500/40 dark:bg-warning-500/10 dark:text-warning-100"
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={processingSettingsPath}>Open processing settings</Link>
            </Button>
          }
        />
      ) : null}
      {updatesAvailable ? (
        <TablecnInlineBanner
          title="Updates available"
          description="Refresh to load the latest changes."
          actions={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={documentsQuery.isFetching}
              >
                {documentsQuery.isFetching ? "Refreshing..." : "Refresh"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setUpdatesAvailable(false)}>
                Dismiss
              </Button>
            </>
          }
        />
      ) : null}
      <TablecnDocumentsTable
        data={documents}
        pageCount={pageCount}
        workspaceId={workspaceId}
        people={people}
        tagOptions={tagOptions}
        onAssign={onAssign}
        onToggleTag={onToggleTag}
        toolbarActions={toolbarActions}
        scrollContainerRef={scrollContainerRef}
        scrollFooter={
          <>
            {hasNextPage ? (
              <div className="flex w-full items-center justify-center py-2 text-xs text-muted-foreground">
                {isFetchingNextPage ? "Loading more documents..." : "Scroll to load more"}
              </div>
            ) : null}
            <div ref={loadMoreRef} className="h-1 w-full" />
          </>
        }
      />
    </div>
  );
}
