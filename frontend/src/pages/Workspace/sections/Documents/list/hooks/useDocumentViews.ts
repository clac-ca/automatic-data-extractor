import { useCallback, useEffect, useMemo, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useQueryState, useQueryStates } from "nuqs";
import type { Table } from "@tanstack/react-table";

import {
  createDocumentView,
  deleteDocumentView,
  listDocumentViews,
  updateDocumentView,
  type DocumentViewRecord,
} from "@/api/documents/views";
import { createScopedStorage } from "@/lib/storage";
import { uiStorageKeys } from "@/lib/uiStorageKeys";

import type { DocumentRow } from "../../shared/types";
import {
  areSnapshotsEqual,
  buildDocumentsQuerySnapshot,
  canonicalizeSnapshotForViewPersistence,
  documentsPageParser,
  documentsQueryParsers,
  documentsViewIdParser,
  encodeSnapshotForViewPersistence,
  hasExplicitListState as queryHasExplicitListState,
  parseViewQueryStateToSnapshot,
} from "../state/queryState";

type ViewVisibility = "system" | "private" | "public";

type TableSnapshot = {
  columnVisibility: Record<string, boolean>;
  columnSizing: Record<string, number>;
  columnOrder: string[];
  columnPinning: { left?: string[]; right?: string[] };
};

const VIEW_QUERY_KEY = "view";
const DEFAULT_ALL_SYSTEM_KEY = "all_documents";

function normalizeTableSnapshot(table: Table<DocumentRow>): TableSnapshot {
  const state = table.getState();
  return {
    columnVisibility: { ...(state.columnVisibility ?? {}) },
    columnSizing: Object.fromEntries(
      Object.entries(state.columnSizing ?? {}).map(([key, value]) => [key, Number(value)]),
    ),
    columnOrder: [...(state.columnOrder ?? [])],
    columnPinning: {
      left: [...(state.columnPinning?.left ?? [])],
      right: [...(state.columnPinning?.right ?? [])],
    },
  };
}

function normalizeViewTableSnapshot(view: DocumentViewRecord): Partial<TableSnapshot> {
  const tableState = (view.tableState ?? {}) as Record<string, unknown>;
  const output: Partial<TableSnapshot> = {};
  if (tableState.columnVisibility && typeof tableState.columnVisibility === "object") {
    output.columnVisibility = tableState.columnVisibility as Record<string, boolean>;
  }
  if (tableState.columnSizing && typeof tableState.columnSizing === "object") {
    output.columnSizing = Object.fromEntries(
      Object.entries(tableState.columnSizing as Record<string, unknown>).map(([key, value]) => [
        key,
        Number(value),
      ]),
    );
  }
  if (Array.isArray(tableState.columnOrder)) {
    output.columnOrder = tableState.columnOrder.filter(
      (value): value is string => typeof value === "string",
    );
  }
  if (tableState.columnPinning && typeof tableState.columnPinning === "object") {
    const pinning = tableState.columnPinning as { left?: unknown; right?: unknown };
    output.columnPinning = {
      left: Array.isArray(pinning.left)
        ? pinning.left.filter((value): value is string => typeof value === "string")
        : [],
      right: Array.isArray(pinning.right)
        ? pinning.right.filter((value): value is string => typeof value === "string")
        : [],
    };
  }
  return output;
}

type SaveAsNewInput = {
  name: string;
  visibility: Extract<ViewVisibility, "private" | "public">;
};

const viewQueryParsers = {
  ...documentsQueryParsers,
  page: documentsPageParser,
};

export function useDocumentViews({
  workspaceId,
  userId,
  table,
  canManagePublicViews,
}: {
  workspaceId: string;
  userId: string;
  table: Table<DocumentRow>;
  canManagePublicViews: boolean;
}) {
  const queryClient = useQueryClient();
  const initializedRef = useRef(false);
  const lastViewStorage = useMemo(
    () => createScopedStorage(uiStorageKeys.documentsLastView(workspaceId)),
    [workspaceId],
  );

  const [viewId, setViewId] = useQueryState(VIEW_QUERY_KEY, documentsViewIdParser);
  const [listQueryState, setListQueryState] = useQueryStates(viewQueryParsers);

  const viewsQuery = useQuery({
    queryKey: ["document-views", workspaceId],
    queryFn: ({ signal }) => listDocumentViews(workspaceId, signal),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  });

  const views = viewsQuery.data?.items ?? [];
  const selectedView = useMemo(
    () => views.find((item) => item.id === viewId) ?? null,
    [views, viewId],
  );

  const currentQuerySnapshot = useMemo(
    () =>
      buildDocumentsQuerySnapshot({
        q: listQueryState.q,
        sort: listQueryState.sort,
        filters: listQueryState.filters,
        joinOperator: listQueryState.joinOperator,
        lifecycle: listQueryState.lifecycle,
      }),
    [
      listQueryState.filters,
      listQueryState.joinOperator,
      listQueryState.lifecycle,
      listQueryState.q,
      listQueryState.sort,
    ],
  );
  const currentCanonicalSnapshot = useMemo(
    () => canonicalizeSnapshotForViewPersistence(currentQuerySnapshot),
    [currentQuerySnapshot],
  );

  const tableState = table.getState();
  const currentTableSnapshot = useMemo(
    () => normalizeTableSnapshot(table),
    [
      table,
      tableState.columnOrder,
      tableState.columnPinning,
      tableState.columnSizing,
      tableState.columnVisibility,
    ],
  );

  const selectedQuerySnapshot = useMemo(
    () =>
      selectedView
        ? parseViewQueryStateToSnapshot((selectedView.queryState ?? {}) as Record<string, unknown>)
        : null,
    [selectedView],
  );
  const selectedCanonicalSnapshot = useMemo(
    () =>
      selectedQuerySnapshot
        ? canonicalizeSnapshotForViewPersistence(selectedQuerySnapshot)
        : null,
    [selectedQuerySnapshot],
  );
  const selectedTableSnapshot = useMemo(
    () => (selectedView ? normalizeViewTableSnapshot(selectedView) : null),
    [selectedView],
  );

  const hasExplicitListState = useMemo(
    () => queryHasExplicitListState(currentQuerySnapshot),
    [currentQuerySnapshot],
  );

  const applyTableSnapshot = useCallback(
    (view: DocumentViewRecord) => {
      const snapshot = normalizeViewTableSnapshot(view);
      if (snapshot.columnVisibility) table.setColumnVisibility(snapshot.columnVisibility);
      if (snapshot.columnSizing) table.setColumnSizing(snapshot.columnSizing);
      if (snapshot.columnOrder) table.setColumnOrder(snapshot.columnOrder);
      if (snapshot.columnPinning) table.setColumnPinning(snapshot.columnPinning);
    },
    [table],
  );

  const applyViewQueryState = useCallback(
    async (view: DocumentViewRecord) => {
      const snapshot = parseViewQueryStateToSnapshot(
        (view.queryState ?? {}) as Record<string, unknown>,
      );

      await Promise.all([
        setViewId(view.id),
        setListQueryState({
          q: snapshot.q,
          sort: snapshot.sort.length > 0 ? snapshot.sort : null,
          filters: snapshot.filters.length > 0 ? snapshot.filters : null,
          joinOperator: snapshot.joinOperator === "and" ? null : snapshot.joinOperator,
          lifecycle: snapshot.lifecycle === "active" ? null : snapshot.lifecycle,
          page: 1,
        }),
      ]);

      table.setColumnFilters([]);
      applyTableSnapshot(view);
      lastViewStorage.set(view.id);
    },
    [
      applyTableSnapshot,
      lastViewStorage,
      setListQueryState,
      setViewId,
      table,
    ],
  );

  useEffect(() => {
    if (!views.length) return;
    if (initializedRef.current) return;
    initializedRef.current = true;

    if (viewId) {
      const existing = views.find((view) => view.id === viewId);
      if (existing) {
        applyTableSnapshot(existing);
        if (!hasExplicitListState) {
          void applyViewQueryState(existing);
        }
        lastViewStorage.set(existing.id);
        return;
      }
      void setViewId(null);
    }

    if (hasExplicitListState) return;

    const lastId = lastViewStorage.get<string>();
    const fallback =
      (lastId ? views.find((view) => view.id === lastId) : null) ??
      views.find((view) => view.systemKey === DEFAULT_ALL_SYSTEM_KEY) ??
      views[0] ??
      null;
    if (fallback) {
      void applyViewQueryState(fallback);
    }
  }, [
    applyTableSnapshot,
    applyViewQueryState,
    hasExplicitListState,
    lastViewStorage,
    setViewId,
    viewId,
    views,
  ]);

  useEffect(() => {
    if (!viewId) return;
    lastViewStorage.set(viewId);
  }, [lastViewStorage, viewId]);

  const canMutateView = useCallback(
    (view: DocumentViewRecord | null) => {
      if (!view) return false;
      if (view.visibility === "system") return false;
      if (view.visibility === "public") return canManagePublicViews;
      return view.ownerUserId === userId;
    },
    [canManagePublicViews, userId],
  );

  const selectedViewCanMutate = canMutateView(selectedView);

  const isEdited = useMemo(() => {
    if (!selectedView || !selectedCanonicalSnapshot) return false;
    const queryEdited = !areSnapshotsEqual(
      currentCanonicalSnapshot,
      selectedCanonicalSnapshot,
    );

    const keys = selectedTableSnapshot ? Object.keys(selectedTableSnapshot) : [];
    const tableEdited = keys.some((key) => {
      const currentValue = (currentTableSnapshot as Record<string, unknown>)[key];
      const selectedValue = (selectedTableSnapshot as Record<string, unknown>)[key];
      return JSON.stringify(currentValue) !== JSON.stringify(selectedValue);
    });

    return queryEdited || tableEdited;
  }, [
    currentCanonicalSnapshot,
    currentTableSnapshot,
    selectedCanonicalSnapshot,
    selectedTableSnapshot,
    selectedView,
  ]);

  const buildCurrentPayload = useCallback(() => {
    const queryState = encodeSnapshotForViewPersistence({
      snapshot: currentQuerySnapshot,
      currentUserId: userId,
    });
    return {
      queryState,
      tableState: currentTableSnapshot,
    };
  }, [currentQuerySnapshot, currentTableSnapshot, userId]);

  const createMutation = useMutation({
    mutationFn: async (input: SaveAsNewInput) => {
      const payload = buildCurrentPayload();
      return createDocumentView(workspaceId, {
        name: input.name,
        visibility: input.visibility,
        queryState: payload.queryState,
        tableState: payload.tableState,
      });
    },
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["document-views", workspaceId] });
      await setViewId(created.id);
      lastViewStorage.set(created.id);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!selectedView) throw new Error("No selected view.");
      const payload = buildCurrentPayload();
      return updateDocumentView(workspaceId, selectedView.id, {
        queryState: payload.queryState,
        tableState: payload.tableState,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["document-views", workspaceId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (target: DocumentViewRecord) => deleteDocumentView(workspaceId, target.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["document-views", workspaceId] });
      const latest = await queryClient.fetchQuery({
        queryKey: ["document-views", workspaceId],
        queryFn: () => listDocumentViews(workspaceId),
      });
      const fallback =
        latest.items.find((view) => view.systemKey === DEFAULT_ALL_SYSTEM_KEY) ??
        latest.items[0] ??
        null;
      if (fallback) {
        await applyViewQueryState(fallback);
        return;
      }
      await setViewId(null);
      lastViewStorage.clear();
    },
  });

  const selectView = useCallback(
    async (target: DocumentViewRecord) => {
      await applyViewQueryState(target);
    },
    [applyViewQueryState],
  );

  const saveSelectedView = useCallback(async () => {
    if (!selectedView || !selectedViewCanMutate) return;
    await updateMutation.mutateAsync();
  }, [selectedView, selectedViewCanMutate, updateMutation]);

  const saveAsNewView = useCallback(
    async (input: SaveAsNewInput) => {
      if (input.visibility === "public" && !canManagePublicViews) {
        throw new Error("Public views require additional permissions.");
      }
      const normalizedName = input.name.trim();
      if (!normalizedName) {
        throw new Error("Name is required.");
      }
      await createMutation.mutateAsync({ ...input, name: normalizedName });
    },
    [canManagePublicViews, createMutation],
  );

  const discardChanges = useCallback(async () => {
    if (!selectedView) return;
    await applyViewQueryState(selectedView);
  }, [applyViewQueryState, selectedView]);

  const removeView = useCallback(
    async (target?: DocumentViewRecord) => {
      const view = target ?? selectedView;
      if (!view) return;
      if (!canMutateView(view)) return;
      await deleteMutation.mutateAsync(view);
    },
    [canMutateView, deleteMutation, selectedView],
  );

  const systemViews = useMemo(
    () => views.filter((view) => view.visibility === "system"),
    [views],
  );
  const publicViews = useMemo(
    () => views.filter((view) => view.visibility === "public"),
    [views],
  );
  const privateViews = useMemo(
    () => views.filter((view) => view.visibility === "private"),
    [views],
  );

  return {
    views,
    systemViews,
    publicViews,
    privateViews,
    selectedViewId: viewId,
    selectedView,
    isLoading: viewsQuery.isLoading,
    isFetching: viewsQuery.isFetching,
    error: viewsQuery.error instanceof Error ? viewsQuery.error.message : null,
    hasExplicitListState,
    isEdited,
    canManagePublicViews,
    canMutateSelectedView: selectedViewCanMutate,
    canMutateView,
    isSaving: updateMutation.isPending,
    isCreating: createMutation.isPending,
    isDeleting: deleteMutation.isPending,
    selectView,
    saveSelectedView,
    saveAsNewView,
    discardChanges,
    removeView,
    refreshViews: viewsQuery.refetch,
  };
}
