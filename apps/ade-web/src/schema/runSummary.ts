export interface RunSummaryRun {
  readonly id: string;
  readonly workspace_id?: string | null;
  readonly configuration_id?: string | null;
  readonly status: "succeeded" | "failed" | "cancelled";
  readonly failure_code?: string | null;
  readonly failure_stage?: string | null;
  readonly failure_message?: string | null;
  readonly engine_version?: string | null;
  readonly config_version?: string | null;
  readonly env_reason?: string | null;
  readonly env_reused?: boolean | null;
  readonly started_at: string;
  readonly completed_at?: string | null;
  readonly duration_seconds?: number | null;
}

export interface RunSummaryCore {
  readonly input_file_count: number;
  readonly input_sheet_count: number;
  readonly table_count: number;
  readonly row_count?: number | null;
  readonly canonical_field_count: number;
  readonly required_field_count: number;
  readonly mapped_field_count: number;
  readonly unmapped_column_count: number;
  readonly validation_issue_count_total: number;
  readonly issue_counts_by_severity: Record<string, number>;
  readonly issue_counts_by_code: Record<string, number>;
}

export interface RunSummaryByFile {
  readonly source_file: string;
  readonly table_count: number;
  readonly row_count?: number | null;
  readonly validation_issue_count_total: number;
  readonly issue_counts_by_severity: Record<string, number>;
  readonly issue_counts_by_code: Record<string, number>;
}

export interface RunSummaryByField {
  readonly field: string;
  readonly label?: string | null;
  readonly required: boolean;
  readonly mapped: boolean;
  readonly max_score?: number | null;
  readonly validation_issue_count_total: number;
  readonly issue_counts_by_severity: Record<string, number>;
  readonly issue_counts_by_code: Record<string, number>;
}

export interface RunSummaryBreakdowns {
  readonly by_file: RunSummaryByFile[];
  readonly by_field: RunSummaryByField[];
}

export interface RunSummaryV1 {
  readonly schema: "ade.run_summary/v1";
  readonly version: string;
  readonly run: RunSummaryRun;
  readonly core: RunSummaryCore;
  readonly breakdowns: RunSummaryBreakdowns;
}
