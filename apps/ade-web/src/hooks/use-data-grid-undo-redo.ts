import * as React from "react";

import { useAsRef } from "@/hooks/use-as-ref";

export type UndoRedoCellUpdate = {
  rowId: string;
  columnId: string;
  previousValue: unknown;
  newValue: unknown;
};

type UndoRedoAction<TData> =
  | {
      type: "cells-update";
      updates: UndoRedoCellUpdate[];
    }
  | {
      type: "rows-add";
      rows: TData[];
    }
  | {
      type: "rows-delete";
      rows: Array<{ row: TData; index: number }>;
    };

export interface UseDataGridUndoRedoProps<TData> {
  data: TData[];
  onDataChange: (data: TData[]) => void;
  getRowId: (row: TData) => string;
  maxHistory?: number;
  enableShortcuts?: boolean;
}

export interface UseDataGridUndoRedoReturn<TData> {
  trackCellsUpdate: (updates: UndoRedoCellUpdate[]) => void;
  trackRowsAdd: (rows: TData[]) => void;
  trackRowsDelete: (rows: TData[]) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  clearHistory: () => void;
}

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  );
}

function applyCellUpdates<TData>(
  data: TData[],
  updates: UndoRedoCellUpdate[],
  getRowId: (row: TData) => string,
  usePrevious: boolean,
) {
  if (updates.length === 0) return data;

  const rowIndexById = new Map<string, number>();
  data.forEach((row, index) => {
    rowIndexById.set(getRowId(row), index);
  });

  const nextData = [...data];

  for (const update of updates) {
    const rowIndex = rowIndexById.get(update.rowId);
    if (rowIndex === undefined) continue;

    const row = nextData[rowIndex] as Record<string, unknown>;
    const nextValue = usePrevious ? update.previousValue : update.newValue;
    nextData[rowIndex] = {
      ...row,
      [update.columnId]: nextValue,
    } as TData;
  }

  return nextData;
}

function removeRowsById<TData>(
  data: TData[],
  rowIds: Set<string>,
  getRowId: (row: TData) => string,
) {
  if (rowIds.size === 0) return data;
  return data.filter((row) => !rowIds.has(getRowId(row)));
}

function insertRowsAtIndices<TData>(
  data: TData[],
  rows: Array<{ row: TData; index: number }>,
) {
  if (rows.length === 0) return data;
  const next = [...data];
  const sorted = [...rows].sort((a, b) => a.index - b.index);
  for (const entry of sorted) {
    const index = Math.max(0, Math.min(entry.index, next.length));
    next.splice(index, 0, entry.row);
  }
  return next;
}

export function useDataGridUndoRedo<TData>({
  data,
  onDataChange,
  getRowId,
  maxHistory = 100,
  enableShortcuts = true,
}: UseDataGridUndoRedoProps<TData>): UseDataGridUndoRedoReturn<TData> {
  const dataRef = useAsRef(data);
  const onDataChangeRef = useAsRef(onDataChange);
  const getRowIdRef = useAsRef(getRowId);

  const undoStackRef = React.useRef<Array<UndoRedoAction<TData>>>([]);
  const redoStackRef = React.useRef<Array<UndoRedoAction<TData>>>([]);

  const [canUndo, setCanUndo] = React.useState(false);
  const [canRedo, setCanRedo] = React.useState(false);

  const updateFlags = React.useCallback(() => {
    setCanUndo(undoStackRef.current.length > 0);
    setCanRedo(redoStackRef.current.length > 0);
  }, []);

  const pushUndo = React.useCallback(
    (action: UndoRedoAction<TData>) => {
      undoStackRef.current.push(action);
      if (undoStackRef.current.length > maxHistory) {
        undoStackRef.current.shift();
      }
      redoStackRef.current = [];
      updateFlags();
    },
    [maxHistory, updateFlags],
  );

  const clearHistory = React.useCallback(() => {
    undoStackRef.current = [];
    redoStackRef.current = [];
    updateFlags();
  }, [updateFlags]);

  const trackCellsUpdate = React.useCallback(
    (updates: UndoRedoCellUpdate[]) => {
      if (updates.length === 0) return;
      pushUndo({ type: "cells-update", updates });
    },
    [pushUndo],
  );

  const trackRowsAdd = React.useCallback(
    (rows: TData[]) => {
      if (rows.length === 0) return;
      pushUndo({ type: "rows-add", rows });
    },
    [pushUndo],
  );

  const trackRowsDelete = React.useCallback(
    (rows: TData[]) => {
      if (rows.length === 0) return;

      const rowIndexById = new Map<string, number>();
      dataRef.current.forEach((row, index) => {
        rowIndexById.set(getRowIdRef.current(row), index);
      });

      const trackedRows = rows.map((row) => ({
        row,
        index: rowIndexById.get(getRowIdRef.current(row)) ?? dataRef.current.length,
      }));

      pushUndo({ type: "rows-delete", rows: trackedRows });
    },
    [dataRef, getRowIdRef, pushUndo],
  );

  const undo = React.useCallback(() => {
    const action = undoStackRef.current.pop();
    if (!action) return;

    const currentData = dataRef.current;
    let nextData = currentData;

    switch (action.type) {
      case "cells-update":
        nextData = applyCellUpdates(
          currentData,
          action.updates,
          getRowIdRef.current,
          true,
        );
        break;
      case "rows-add": {
        const rowIds = new Set(
          action.rows.map((row) => getRowIdRef.current(row)),
        );
        nextData = removeRowsById(
          currentData,
          rowIds,
          getRowIdRef.current,
        );
        break;
      }
      case "rows-delete":
        nextData = insertRowsAtIndices(currentData, action.rows);
        break;
      default:
        break;
    }

    redoStackRef.current.push(action);
    updateFlags();
    onDataChangeRef.current(nextData);
  }, [dataRef, getRowIdRef, onDataChangeRef, updateFlags]);

  const redo = React.useCallback(() => {
    const action = redoStackRef.current.pop();
    if (!action) return;

    const currentData = dataRef.current;
    let nextData = currentData;

    switch (action.type) {
      case "cells-update":
        nextData = applyCellUpdates(
          currentData,
          action.updates,
          getRowIdRef.current,
          false,
        );
        break;
      case "rows-add": {
        const existingIds = new Set(
          currentData.map((row) => getRowIdRef.current(row)),
        );
        const rowsToAdd = action.rows.filter(
          (row) => !existingIds.has(getRowIdRef.current(row)),
        );
        nextData = [...currentData, ...rowsToAdd];
        break;
      }
      case "rows-delete": {
        const rowIds = new Set(
          action.rows.map((entry) => getRowIdRef.current(entry.row)),
        );
        nextData = removeRowsById(
          currentData,
          rowIds,
          getRowIdRef.current,
        );
        break;
      }
      default:
        break;
    }

    undoStackRef.current.push(action);
    updateFlags();
    onDataChangeRef.current(nextData);
  }, [dataRef, getRowIdRef, onDataChangeRef, updateFlags]);

  React.useEffect(() => {
    if (!enableShortcuts) return undefined;

    function onKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented || isEditableTarget(event.target)) return;

      const isMod = event.metaKey || event.ctrlKey;
      if (!isMod) return;

      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey) {
        event.preventDefault();
        undo();
      } else if (key === "z" && event.shiftKey) {
        event.preventDefault();
        redo();
      } else if (key === "y") {
        event.preventDefault();
        redo();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enableShortcuts, redo, undo]);

  return {
    trackCellsUpdate,
    trackRowsAdd,
    trackRowsDelete,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  };
}
