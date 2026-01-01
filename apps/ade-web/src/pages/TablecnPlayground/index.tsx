import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchWorkspaceDocuments, patchWorkspaceDocument, type DocumentPageResult } from "@api/documents";
import { documentChangesStreamUrl, streamDocumentChanges } from "@api/documents/changes";
import { patchDocumentTags, fetchTagCatalog } from "@api/documents/tags";
import { ApiError } from "@api/errors";
import { listWorkspaceMembers } from "@api/workspaces/api";
import { RequireSession } from "@components/providers/auth/RequireSession";
import { useSession } from "@components/providers/auth/SessionContext";
import { useNotifications } from "@components/providers/notifications";
import { PageState } from "@components/layouts/page-state";
import { Button } from "@components/ui/button";
import { useWorkspacesQuery } from "@hooks/workspaces";
import { useNavigate } from "@app/navigation/history";
import { readPreferredWorkspaceId } from "@lib/workspacePreferences";
import { shortId } from "@pages/Workspace/sections/Documents/utils";
import { mergeDocumentChangeIntoPages } from "@pages/Workspace/sections/Documents/changeFeed";
import type { WorkspacePerson } from "@pages/Workspace/sections/Documents/types";
import { TablecnDocumentsTable } from "./components/TablecnDocumentsTable";
import { TablecnPlaygroundLayout } from "./components/TablecnPlaygroundLayout";
import { useDocumentsListParams } from "./hooks/useDocumentsListParams";
import type { DocumentChangeEntry } from "./types";
import { normalizeDocumentsFilters, normalizeDocumentsSort } from "./utils";

export default function TablecnPlaygroundScreen() {
  return (
    <RequireSession>
      <TablecnDocumentsPlayground />
    </RequireSession>
  );
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
  const currentUser = useMemo(
    () => ({
      id: session.user.id,
      email: session.user.email,
      label: session.user.display_name || session.user.email || "You",
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );

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

  return <TablecnDocumentsContainer workspaceId={workspace.id} currentUser={currentUser} />;
}

type CurrentUser = {
  id: string;
  email: string;
  label: string;
};

function TablecnDocumentsContainer({
  workspaceId,
  currentUser,
}: {
  workspaceId: string;
  currentUser: CurrentUser;
}) {
  const queryClient = useQueryClient();
  const { notifyToast } = useNotifications();
  const [updatesAvailable, setUpdatesAvailable] = useState(false);
  const lastCursorRef = useRef<string | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const { page, perPage, sort, filters, joinOperator, q } =
    useDocumentsListParams();
  const normalizedSort = useMemo(() => normalizeDocumentsSort(sort), [sort]);
  const normalizedFilters = useMemo(
    () => normalizeDocumentsFilters(filters),
    [filters],
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
      page,
    ],
    [workspaceId, perPage, normalizedSort, filtersKey, joinOperator, q, page],
  );

  const documentsQuery = useInfiniteQuery<DocumentPageResult>({
    queryKey,
    initialPageParam: page > 0 ? page : 1,
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
    [queryClient, queryKey],
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
      let shouldPrompt = Boolean(change.requiresRefresh);

      queryClient.setQueryData(queryKey, (existing: typeof documentsQuery.data | undefined) => {
        if (!existing) {
          return existing;
        }
        const result = mergeDocumentChangeIntoPages(existing, change);
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
  }, [changesCursor, filtersKey, joinOperator, page, perPage, q, normalizedSort, workspaceId]);

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
      { rootMargin: "200px" },
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

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

  const pageCount = documentsQuery.data?.pages[0]?.pageCount ?? 1;
  const handleRefresh = () => {
    setUpdatesAvailable(false);
    void documentsQuery.refetch();
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
        data={documents}
        pageCount={pageCount}
        workspaceId={workspaceId}
        people={people}
        tagOptions={tagOptions}
        onAssign={onAssign}
        onToggleTag={onToggleTag}
      />
      {hasNextPage ? (
        <div className="flex items-center justify-center py-2 text-xs text-muted-foreground">
          {isFetchingNextPage ? "Loading more documents..." : "Scroll to load more"}
        </div>
      ) : null}
      <div ref={loadMoreRef} className="h-1" />
    </TablecnPlaygroundLayout>
  );
}
