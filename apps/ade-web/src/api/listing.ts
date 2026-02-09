export type FilterOperator =
  | "eq"
  | "ne"
  | "in"
  | "inArray"
  | "notIn"
  | "notInArray"
  | "lt"
  | "lte"
  | "gt"
  | "gte"
  | "iLike"
  | "notILike"
  | "isEmpty"
  | "isNotEmpty"
  | "between"
  | "isBetween"
  | "isRelativeToToday";

export type FilterJoinOperator = "and" | "or";

export type FilterValue =
  | string
  | number
  | boolean
  | string[]
  | number[]
  | boolean[]
  | null;

export type FilterItem = {
  id: string;
  operator: FilterOperator;
  value?: FilterValue;
};

export type ListQueryParams = {
  limit?: number;
  cursor?: string;
  sort?: string;
  filters?: string;
  joinOperator?: FilterJoinOperator;
  q?: string;
  includeTotal?: boolean;
  includeFacets?: boolean;
};

export function encodeFilters(filters?: readonly FilterItem[]): string | undefined {
  if (!filters || filters.length === 0) {
    return undefined;
  }
  return JSON.stringify(filters);
}

export function buildListQuery(options: {
  limit?: number;
  cursor?: string | null;
  sort?: string | null;
  filters?: FilterItem[] | string | null;
  joinOperator?: FilterJoinOperator;
  q?: string | null;
  includeTotal?: boolean;
  includeFacets?: boolean;
}): ListQueryParams {
  const query: ListQueryParams = {};
  if (typeof options.limit === "number" && options.limit > 0) {
    query.limit = options.limit;
  }
  if (options.cursor) {
    query.cursor = options.cursor;
  }
  if (options.sort) {
    query.sort = options.sort;
  }
  const encoded =
    typeof options.filters === "string"
      ? options.filters.trim()
      : encodeFilters(options.filters);
  if (encoded) {
    query.filters = encoded;
    if (options.joinOperator) {
      query.joinOperator = options.joinOperator;
    }
  }
  if (options.q) {
    query.q = options.q;
  }
  if (typeof options.includeTotal === "boolean") {
    query.includeTotal = options.includeTotal;
  }
  if (typeof options.includeFacets === "boolean") {
    query.includeFacets = options.includeFacets;
  }
  return query;
}
