import { useMemo } from "react";
import { X } from "lucide-react";
import { useQueryState } from "nuqs";
import type { Table } from "@tanstack/react-table";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ExtendedColumnFilter } from "@/types/data-table";

import type { DocumentRow } from "../../shared/types";
import {
  documentsFiltersParser,
  documentsJoinOperatorParser,
  documentsLifecycleParser,
} from "../state/queryState";

type ActiveFilter = {
  key: string;
  id: string;
  label: string;
  value: string;
};

function stringifyFilterValue(value: ExtendedColumnFilter<DocumentRow>["value"]) {
  if (Array.isArray(value)) {
    const visibleValues = value.filter(Boolean).slice(0, 3);
    const suffix = value.length > visibleValues.length ? ` +${value.length - visibleValues.length}` : "";
    return `${visibleValues.join(", ")}${suffix}`;
  }
  if (value === undefined || value === null || value === "") return "Any";
  return String(value);
}

export function DocumentsActiveFiltersRail({
  table,
}: {
  table: Table<DocumentRow>;
}) {
  const [filters, setFilters] = useQueryState("filters", documentsFiltersParser);
  const [joinOperator, setJoinOperator] = useQueryState("joinOperator", documentsJoinOperatorParser);
  const [lifecycle, setLifecycle] = useQueryState("lifecycle", documentsLifecycleParser);

  const activeFilters = useMemo<ActiveFilter[]>(() => {
    const entries = (filters ?? []) as ExtendedColumnFilter<DocumentRow>[];
    return entries.map((filter) => {
      const label = table.getColumn(filter.id)?.columnDef.meta?.label ?? filter.id;
      return {
        key: filter.filterId,
        id: filter.id,
        label,
        value: stringifyFilterValue(filter.value),
      };
    });
  }, [filters, table]);

  const clearFilter = (filterKey: string) => {
    const next = (filters ?? []).filter((item) => item.filterId !== filterKey);
    void setFilters(next.length ? next : null);
    if (next.length <= 1) {
      void setJoinOperator("and");
    }
  };

  const showDeleted = lifecycle === "deleted";
  const hasActiveFilters = activeFilters.length > 0 || showDeleted;

  return (
    <div className="documents-filter-rail flex min-h-10 flex-wrap items-center gap-2 rounded-md border border-border/60 bg-muted/20 px-2 py-1.5">
      <span className="text-xs font-medium text-muted-foreground">Active filters</span>
      {activeFilters.length > 1 && joinOperator === "or" ? (
        <Badge variant="secondary" className="h-6 px-2 text-[11px]">
          Match any
        </Badge>
      ) : null}
      {showDeleted ? (
        <Badge variant="secondary" className="h-6 gap-1 px-2 text-[11px]">
          Deleted
          <button
            type="button"
            aria-label="Remove Deleted filter"
            className="inline-flex items-center"
            onClick={() => {
              void setLifecycle("active");
            }}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ) : null}
      {activeFilters.map((filter) => (
        <Badge key={filter.key} variant="secondary" className="h-6 gap-1 px-2 text-[11px]">
          <span className="font-medium">{filter.label}:</span>
          <span className="max-w-[180px] truncate">{filter.value}</span>
          <button
            type="button"
            aria-label={`Remove ${filter.label} filter`}
            className="inline-flex items-center"
            onClick={() => clearFilter(filter.key)}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
      <div className="ml-auto">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => {
            void setFilters(null);
            void setJoinOperator("and");
            void setLifecycle("active");
          }}
          disabled={!hasActiveFilters}
        >
          Clear all
        </Button>
      </div>
    </div>
  );
}
