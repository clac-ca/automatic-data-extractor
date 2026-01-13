import type { components } from "@schema";
import type { FilterItem } from "@api/listing";

export type DocumentListRow = components["schemas"]["DocumentListRow"];

export type DocumentsListParams = {
  page: number;
  perPage: number;
  sort: string | null;
  filters: FilterItem[] | null;
  joinOperator: "and" | "or" | null;
};
