"use client";

import {
  type ColumnFiltersState,
  type ColumnSizingState,
  getCoreRowModel,
  getFacetedMinMaxValues,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
  type TableOptions,
  type TableState,
  type Updater,
  useReactTable,
  type VisibilityState,
} from "@tanstack/react-table";
import * as React from "react";

import { useSearchParams } from "@app/navigation/urlState";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";
import {
  parseSortingState,
  serializeSortingState,
} from "@/lib/parsers";
import { createScopedStorage } from "@/lib/storage";
import type { ExtendedColumnSort, QueryKeys } from "@/types/data-table";

const PAGE_KEY = "page";
const PER_PAGE_KEY = "perPage";
const SORT_KEY = "sort";
const FILTERS_KEY = "filters";
const JOIN_OPERATOR_KEY = "joinOperator";
const ARRAY_SEPARATOR = ",";
const DEBOUNCE_MS = 300;
const THROTTLE_MS = 50;

function parseNumberParam(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function isSortingEqual<TData>(
  left: ExtendedColumnSort<TData>[],
  right: ExtendedColumnSort<TData>[],
) {
  return (
    left.length === right.length &&
    left.every(
      (item, index) =>
        item.id === right[index]?.id && item.desc === right[index]?.desc,
    )
  );
}

function isExplicitEmptySort(value: string) {
  const trimmed = value.trim();
  if (!trimmed.startsWith("[")) return false;
  try {
    const parsed = JSON.parse(trimmed);
    return Array.isArray(parsed) && parsed.length === 0;
  } catch {
    return false;
  }
}

interface UseDataTableProps<TData>
  extends Omit<
      TableOptions<TData>,
      | "state"
      | "pageCount"
      | "getCoreRowModel"
      | "manualFiltering"
      | "manualPagination"
      | "manualSorting"
    >,
    Required<Pick<TableOptions<TData>, "pageCount">> {
  initialState?: Omit<Partial<TableState>, "sorting"> & {
    sorting?: ExtendedColumnSort<TData>[];
  };
  queryKeys?: Partial<QueryKeys>;
  history?: "push" | "replace";
  debounceMs?: number;
  throttleMs?: number;
  clearOnDefault?: boolean;
  enableAdvancedFilter?: boolean;
  enableColumnResizing?: boolean;
  columnSizingKey?: string;
  scroll?: boolean;
  shallow?: boolean;
  startTransition?: React.TransitionStartFunction;
}

export function useDataTable<TData>(props: UseDataTableProps<TData>) {
  const {
    columns,
    pageCount = -1,
    initialState,
    queryKeys,
    history = "replace",
    debounceMs = DEBOUNCE_MS,
    throttleMs = THROTTLE_MS,
    clearOnDefault = false,
    enableAdvancedFilter = false,
    enableColumnResizing = false,
    columnSizingKey,
    scroll: _scroll = false,
    shallow = true,
    startTransition,
    ...tableProps
  } = props;
  const pageKey = queryKeys?.page ?? PAGE_KEY;
  const perPageKey = queryKeys?.perPage ?? PER_PAGE_KEY;
  const sortKey = queryKeys?.sort ?? SORT_KEY;
  const filtersKey = queryKeys?.filters ?? FILTERS_KEY;
  const joinOperatorKey = queryKeys?.joinOperator ?? JOIN_OPERATOR_KEY;

  const replace = history !== "push";
  const [searchParams, setSearchParams] = useSearchParams();

  const defaultPageSize = initialState?.pagination?.pageSize ?? 10;

  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>(
    initialState?.rowSelection ?? {},
  );
  const [columnVisibility, setColumnVisibility] =
    React.useState<VisibilityState>(initialState?.columnVisibility ?? {});
  const columnSizingStorage = React.useMemo(
    () => (columnSizingKey ? createScopedStorage(columnSizingKey) : null),
    [columnSizingKey],
  );
  const [columnSizing, setColumnSizing] = React.useState<ColumnSizingState>(() => {
    if (!columnSizingStorage) {
      return initialState?.columnSizing ?? {};
    }
    const stored = columnSizingStorage.get<ColumnSizingState>();
    return stored ?? initialState?.columnSizing ?? {};
  });

  const page = React.useMemo(
    () => parseNumberParam(searchParams.get(pageKey), 1),
    [searchParams, pageKey],
  );
  const perPage = React.useMemo(
    () => parseNumberParam(searchParams.get(perPageKey), defaultPageSize),
    [searchParams, perPageKey, defaultPageSize],
  );

  const pagination: PaginationState = React.useMemo(() => {
    return {
      pageIndex: page - 1, // zero-based index -> one-based index
      pageSize: perPage,
    };
  }, [page, perPage]);

  const setParams = React.useCallback(
    (
      updater: (params: URLSearchParams) => URLSearchParams,
      opts: { replace?: boolean } = {},
    ) => {
      const applyUpdate = () =>
        setSearchParams((prev) => updater(new URLSearchParams(prev)), {
          replace: opts.replace ?? replace,
        });

      if (startTransition) {
        startTransition(() => applyUpdate());
      } else {
        applyUpdate();
      }
    },
    [replace, setSearchParams, startTransition],
  );

  const setPage = React.useCallback(
    (nextPage: number) => {
      setParams((params) => {
        if (clearOnDefault && nextPage === 1) {
          params.delete(pageKey);
        } else {
          params.set(pageKey, String(nextPage));
        }
        return params;
      });
    },
    [clearOnDefault, pageKey, setParams],
  );

  const setPerPage = React.useCallback(
    (nextPerPage: number) => {
      setParams((params) => {
        if (clearOnDefault && nextPerPage === defaultPageSize) {
          params.delete(perPageKey);
        } else {
          params.set(perPageKey, String(nextPerPage));
        }
        return params;
      });
    },
    [clearOnDefault, defaultPageSize, perPageKey, setParams],
  );

  const onPaginationChange = React.useCallback(
    (updaterOrValue: Updater<PaginationState>) => {
      if (typeof updaterOrValue === "function") {
        const newPagination = updaterOrValue(pagination);
        setPage(newPagination.pageIndex + 1);
        setPerPage(newPagination.pageSize);
      } else {
        setPage(updaterOrValue.pageIndex + 1);
        setPerPage(updaterOrValue.pageSize);
      }
    },
    [pagination, setPage, setPerPage],
  );

  const columnIds = React.useMemo(() => {
    return new Set(
      columns.map((column) => column.id).filter(Boolean) as string[],
    );
  }, [columns]);

  const sorting = React.useMemo(() => {
    const rawSort = searchParams.get(sortKey);
    if (!rawSort) {
      return initialState?.sorting ?? [];
    }
    const parsed = parseSortingState<TData>(rawSort, columnIds);
    if (parsed.length > 0 || isExplicitEmptySort(rawSort)) {
      return parsed;
    }
    return initialState?.sorting ?? [];
  }, [searchParams, sortKey, columnIds, initialState?.sorting]);

  const setSorting = React.useCallback(
    (nextSorting: ExtendedColumnSort<TData>[]) => {
      const defaultSorting = initialState?.sorting ?? [];
      setParams((params) => {
        if (clearOnDefault && isSortingEqual(nextSorting, defaultSorting)) {
          params.delete(sortKey);
        } else {
          params.set(sortKey, serializeSortingState(nextSorting));
        }
        return params;
      });
    },
    [clearOnDefault, initialState?.sorting, setParams, sortKey],
  );

  const onSortingChange = React.useCallback(
    (updaterOrValue: Updater<SortingState>) => {
      if (typeof updaterOrValue === "function") {
        const newSorting = updaterOrValue(sorting);
        setSorting(newSorting as ExtendedColumnSort<TData>[]);
      } else {
        setSorting(updaterOrValue as ExtendedColumnSort<TData>[]);
      }
    },
    [sorting, setSorting],
  );

  const filterableColumns = React.useMemo(() => {
    if (enableAdvancedFilter) return [];

    return columns.filter((column) => column.enableColumnFilter);
  }, [columns, enableAdvancedFilter]);

  const filterValues = React.useMemo(() => {
    if (enableAdvancedFilter) return {} as Record<string, string | string[] | null>;

    return filterableColumns.reduce<
      Record<string, string | string[] | null>
    >((acc, column) => {
      const key = column.id ?? "";
      if (!key) return acc;
      const rawValue = searchParams.get(key);
      if (!rawValue) {
        acc[key] = null;
        return acc;
      }

      if (column.meta?.options) {
        acc[key] = rawValue.split(ARRAY_SEPARATOR).filter(Boolean);
      } else {
        acc[key] = rawValue;
      }
      return acc;
    }, {});
  }, [enableAdvancedFilter, filterableColumns, searchParams]);

  const setFilterValues = React.useCallback(
    (values: Record<string, string | string[] | null>) => {
      setParams((params) => {
        for (const [key, value] of Object.entries(values)) {
          if (
            value === null ||
            (Array.isArray(value) && value.length === 0) ||
            (typeof value === "string" && value.trim() === "")
          ) {
            params.delete(key);
          } else {
            const serialized = Array.isArray(value)
              ? value.join(ARRAY_SEPARATOR)
              : value;
            params.set(key, serialized);
          }
        }

        if (clearOnDefault) {
          params.delete(pageKey);
        } else {
          params.set(pageKey, "1");
        }

        return params;
      });
    },
    [clearOnDefault, pageKey, setParams],
  );

  const debouncedSetFilterValues = useDebouncedCallback(
    (values: typeof filterValues) => {
      setFilterValues(values);
    },
    debounceMs,
  );

  const initialColumnFilters: ColumnFiltersState = React.useMemo(() => {
    if (enableAdvancedFilter) return [];

    return Object.entries(filterValues).reduce<ColumnFiltersState>(
      (filters, [key, value]) => {
        if (value !== null) {
          const processedValue = Array.isArray(value)
            ? value
            : typeof value === "string" && /[^a-zA-Z0-9]/.test(value)
              ? value.split(/[^a-zA-Z0-9]+/).filter(Boolean)
              : [value];

          filters.push({
            id: key,
            value: processedValue,
          });
        }
        return filters;
      },
      [],
    );
  }, [filterValues, enableAdvancedFilter]);

  const [columnFilters, setColumnFilters] =
    React.useState<ColumnFiltersState>(initialColumnFilters);

  const onColumnFiltersChange = React.useCallback(
    (updaterOrValue: Updater<ColumnFiltersState>) => {
      if (enableAdvancedFilter) return;

      setColumnFilters((prev) => {
        const next =
          typeof updaterOrValue === "function"
            ? updaterOrValue(prev)
            : updaterOrValue;

        const filterUpdates = next.reduce<
          Record<string, string | string[] | null>
        >((acc, filter) => {
          if (filterableColumns.find((column) => column.id === filter.id)) {
            acc[filter.id] = filter.value as string | string[];
          }
          return acc;
        }, {});

        for (const prevFilter of prev) {
          if (!next.some((filter) => filter.id === prevFilter.id)) {
            filterUpdates[prevFilter.id] = null;
          }
        }

        debouncedSetFilterValues(filterUpdates);
        return next;
      });
    },
    [debouncedSetFilterValues, filterableColumns, enableAdvancedFilter],
  );

  React.useEffect(() => {
    if (!columnSizingStorage) {
      return;
    }
    columnSizingStorage.set(columnSizing);
  }, [columnSizing, columnSizingStorage]);

  const table = useReactTable({
    ...tableProps,
    columns,
    initialState,
    pageCount,
    state: {
      pagination,
      sorting,
      columnVisibility,
      rowSelection,
      columnFilters,
      columnSizing,
    },
    defaultColumn: {
      ...tableProps.defaultColumn,
      enableColumnFilter: false,
    },
    enableColumnResizing,
    columnResizeMode: enableColumnResizing ? "onChange" : undefined,
    columnResizeDirection: "ltr",
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onPaginationChange,
    onSortingChange,
    onColumnFiltersChange,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
    getFacetedMinMaxValues: getFacetedMinMaxValues(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    meta: {
      ...tableProps.meta,
      queryKeys: {
        page: pageKey,
        perPage: perPageKey,
        sort: sortKey,
        filters: filtersKey,
        joinOperator: joinOperatorKey,
      },
    },
  });

  return { table, shallow, debounceMs, throttleMs, history, startTransition };
}
