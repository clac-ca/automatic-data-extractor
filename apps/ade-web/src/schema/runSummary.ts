export type SummaryScope = "run" | "file" | "sheet" | "table";

export interface RowCounts {
  readonly total: number;
  readonly empty: number;
  readonly non_empty: number;
}

export interface ColumnCounts {
  readonly physical_total: number;
  readonly physical_empty: number;
  readonly physical_non_empty: number;
  readonly distinct_headers: number;
  readonly distinct_headers_mapped: number;
  readonly distinct_headers_unmapped: number;
}

export interface FieldCounts {
  readonly total: number;
  readonly required: number;
  readonly mapped: number;
  readonly unmapped: number;
  readonly required_mapped: number;
  readonly required_unmapped: number;
}

export interface Counts {
  readonly files?: Record<string, number> | null;
  readonly sheets?: Record<string, number> | null;
  readonly tables?: Record<string, number> | null;
  readonly rows: RowCounts;
  readonly columns: ColumnCounts;
  readonly fields: FieldCounts;
}

export interface FieldSummaryTable {
  readonly field: string;
  readonly label?: string | null;
  readonly required: boolean;
  readonly mapped: boolean;
  readonly score?: number | null;
  readonly source_column_index?: number | null;
  readonly header?: string | null;
}

export interface FieldSummaryAggregate {
  readonly field: string;
  readonly label?: string | null;
  readonly required: boolean;
  readonly mapped: boolean;
  readonly max_score?: number | null;
  readonly tables_mapped?: number | null;
  readonly sheets_mapped?: number | null;
  readonly files_mapped?: number | null;
}

export interface ColumnSummaryTable {
  readonly source_column_index: number;
  readonly header: string;
  readonly empty: boolean;
  readonly non_empty_row_count: number;
  readonly mapped: boolean;
  readonly mapped_field?: string | null;
  readonly mapped_field_label?: string | null;
  readonly score?: number | null;
  readonly output_header?: string | null;
}

export interface ColumnSummaryDistinct {
  readonly header: string;
  readonly header_normalized: string;
  readonly occurrences: Record<string, number>;
  readonly mapped: boolean;
  readonly mapped_fields: string[];
  readonly mapped_fields_counts: Record<string, number>;
}

export interface ValidationSummary {
  readonly rows_evaluated: number;
  readonly issues_total: number;
  readonly issues_by_severity: Record<string, number>;
  readonly issues_by_code: Record<string, number>;
  readonly issues_by_field: Record<string, number>;
  readonly max_severity?: string | null;
}

export interface BaseSummary<Scope extends SummaryScope, FieldSummary, ColumnSummary> {
  readonly schema_id: string;
  readonly schema_version: string;
  readonly scope: Scope;
  readonly id: string;
  readonly parent_ids: Record<string, string>;
  readonly source: Record<string, unknown>;
  readonly counts: Counts;
  readonly fields: FieldSummary[];
  readonly columns: ColumnSummary[];
  readonly validation: ValidationSummary;
  readonly details: Record<string, unknown>;
}

export type TableSummary = BaseSummary<"table", FieldSummaryTable, ColumnSummaryTable>;
export type SheetSummary = BaseSummary<"sheet", FieldSummaryAggregate, ColumnSummaryDistinct>;
export type FileSummary = BaseSummary<"file", FieldSummaryAggregate, ColumnSummaryDistinct>;
export type RunSummary = BaseSummary<"run", FieldSummaryAggregate, ColumnSummaryDistinct>;
