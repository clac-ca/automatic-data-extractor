export interface ArtifactScoreContribution {
  readonly detector: string;
  readonly delta: number;
}

export interface ArtifactMappedColumn {
  readonly field: string;
  readonly header: string;
  readonly source_column_index: number;
  readonly score: number;
  readonly contributions: ArtifactScoreContribution[];
}

export interface ArtifactUnmappedColumn {
  readonly header: string;
  readonly source_column_index: number;
  readonly output_header: string;
}

export interface ArtifactValidationIssue {
  readonly row_index: number;
  readonly field: string;
  readonly code: string;
  readonly severity: string;
  readonly message?: string | null;
  readonly details?: Record<string, unknown> | null;
}

export interface ArtifactTableHeader {
  readonly row_index: number;
  readonly cells: string[];
}

export interface ArtifactTable {
  readonly source_file: string;
  readonly source_sheet?: string | null;
  readonly table_index: number;
  readonly header: ArtifactTableHeader;
  readonly mapped_columns: ArtifactMappedColumn[];
  readonly unmapped_columns: ArtifactUnmappedColumn[];
  readonly validation_issues: ArtifactValidationIssue[];
}

export interface ArtifactNote {
  readonly timestamp: string;
  readonly level: string;
  readonly message: string;
  readonly details?: Record<string, unknown> | null;
}

export interface ArtifactRunMetadata {
  readonly id: string;
  readonly status: string;
  readonly started_at: string;
  readonly completed_at?: string | null;
  readonly outputs: string[];
  readonly engine_version: string;
  readonly error?: {
    readonly code: string;
    readonly stage?: string | null;
    readonly message: string;
    readonly details?: Record<string, unknown> | null;
  } | null;
}

export interface ArtifactConfigMetadata {
  readonly schema: string;
  readonly version: string;
  readonly name?: string | null;
}

export interface ArtifactV1 {
  readonly schema: string;
  readonly version: string;
  readonly run: ArtifactRunMetadata;
  readonly config: ArtifactConfigMetadata;
  readonly tables: ArtifactTable[];
  readonly notes: ArtifactNote[];
}
