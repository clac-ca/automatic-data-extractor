import { z } from "zod";

import { dataTableConfig } from "@/config/data-table";

import type {
  ExtendedColumnFilter,
  ExtendedColumnSort,
} from "@/types/data-table";

const sortingItemSchema = z.object({
  id: z.string(),
  desc: z.boolean(),
});

function normalizeKeys(columnIds?: string[] | Set<string>) {
  if (!columnIds) return null;
  return columnIds instanceof Set ? columnIds : new Set(columnIds);
}

export const parseSortingState = <TData>(
  value: string | null,
  columnIds?: string[] | Set<string>,
): ExtendedColumnSort<TData>[] => {
  if (!value) return [];
  const validKeys = normalizeKeys(columnIds);
  try {
    const parsed = JSON.parse(value);
    const result = z.array(sortingItemSchema).safeParse(parsed);

    if (!result.success) return [];

    if (validKeys && result.data.some((item) => !validKeys.has(item.id))) {
      return [];
    }

    return result.data as ExtendedColumnSort<TData>[];
  } catch {
    return [];
  }
};

export const serializeSortingState = <TData>(
  value: ExtendedColumnSort<TData>[],
): string => JSON.stringify(value);

const filterItemSchema = z.object({
  id: z.string(),
  value: z.union([z.string(), z.array(z.string())]),
  variant: z.enum(dataTableConfig.filterVariants),
  operator: z.enum(dataTableConfig.operators),
  filterId: z.string(),
});

export type FilterItemSchema = z.infer<typeof filterItemSchema>;

export const parseFiltersState = <TData>(
  value: string | null,
  columnIds?: string[] | Set<string>,
): ExtendedColumnFilter<TData>[] => {
  if (!value) return [];
  const validKeys = normalizeKeys(columnIds);
  try {
    const parsed = JSON.parse(value);
    const result = z.array(filterItemSchema).safeParse(parsed);

    if (!result.success) return [];

    if (validKeys && result.data.some((item) => !validKeys.has(item.id))) {
      return [];
    }

    return result.data as ExtendedColumnFilter<TData>[];
  } catch {
    return [];
  }
};

export const serializeFiltersState = <TData>(
  value: ExtendedColumnFilter<TData>[],
): string => JSON.stringify(value);
