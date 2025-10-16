export interface ConfigurationRecord {
  readonly configuration_id: string;
  readonly workspace_id: string;
  readonly title: string;
  readonly version: number;
  readonly is_active: boolean;
  readonly activated_at?: string | null;
  readonly payload: Record<string, unknown>;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface ConfigurationColumn {
  readonly configuration_id: string;
  readonly canonical_key: string;
  readonly ordinal: number;
  readonly display_label: string;
  readonly header_color?: string | null;
  readonly width?: number | null;
  readonly required: boolean;
  readonly enabled: boolean;
  readonly script_version_id?: string | null;
  readonly params: Record<string, unknown>;
  readonly script_version?: ConfigurationScriptVersion | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface ConfigurationScriptVersion {
  readonly script_version_id: string;
  readonly configuration_id: string;
  readonly canonical_key: string;
  readonly version: number;
  readonly language: string;
  readonly code?: string | null;
  readonly code_sha256: string;
  readonly doc_name?: string | null;
  readonly doc_description?: string | null;
  readonly doc_declared_version?: number | null;
  readonly validated_at?: string | null;
  readonly validation_errors?: Record<string, unknown> | null;
  readonly created_by_user_id?: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface ConfigurationCreatePayload {
  readonly title: string;
  readonly payload?: Record<string, unknown>;
  readonly clone_from_configuration_id?: string;
  readonly clone_from_active?: boolean;
}

export interface ConfigurationColumnInput {
  readonly canonical_key: string;
  readonly ordinal: number;
  readonly display_label: string;
  readonly header_color?: string | null;
  readonly width?: number | null;
  readonly required: boolean;
  readonly enabled: boolean;
  readonly script_version_id?: string | null;
  readonly params: Record<string, unknown>;
}

export interface ConfigurationScriptVersionInput {
  readonly canonical_key: string;
  readonly language?: string;
  readonly code: string;
}

export interface ConfigurationColumnBindingUpdate {
  readonly script_version_id?: string | null;
  readonly params?: Record<string, unknown> | null;
  readonly enabled?: boolean;
  readonly required?: boolean;
}
