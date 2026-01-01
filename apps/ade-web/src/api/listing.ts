export type FilterOperator =
  | "eq"
  | "ne"
  | "in"
  | "notIn"
  | "lt"
  | "lte"
  | "gt"
  | "gte"
  | "iLike"
  | "notILike"
  | "isEmpty"
  | "isNotEmpty"
  | "between";

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
  page?: number;
  perPage?: number;
  sort?: string;
  filters?: string;
  joinOperator?: FilterJoinOperator;
  q?: string;
};

export function encodeFilters(filters?: readonly FilterItem[]): string | undefined {
  if (!filters || filters.length === 0) {
    return undefined;
  }
  return JSON.stringify(filters);
}

export function buildListQuery(options: {
  page?: number;
  perPage?: number;
  sort?: string | null;
  filters?: FilterItem[];
  joinOperator?: FilterJoinOperator;
  q?: string | null;
}): ListQueryParams {
  const query: ListQueryParams = {};
  if (typeof options.page === "number" && options.page > 0) {
    query.page = options.page;
  }
  if (typeof options.perPage === "number" && options.perPage > 0) {
    query.perPage = options.perPage;
  }
  if (options.sort) {
    query.sort = options.sort;
  }
  const encoded = encodeFilters(options.filters);
  if (encoded) {
    query.filters = encoded;
    if (options.joinOperator) {
      query.joinOperator = options.joinOperator;
    }
  }
  if (options.q) {
    query.q = options.q;
  }
  return query;
}
