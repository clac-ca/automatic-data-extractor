"""Initial ADE schema (Postgres) for launch baseline.

Notes:
- Defines a frozen schema snapshot using explicit DDL (no ORM create_all).
- UUID primary keys use Postgres uuidv7() defaults.
- Enums use VARCHAR + CHECK constraints (native_enum=False).
- JSON payloads are stored as JSONB.
- Includes publish-era schema primitives (``RunOperation.PUBLISH``,
  ``configurations.published_digest``, and active publish run index).
- Seeds singleton ``application_settings`` row ``id=1`` for runtime settings.
- Installs run queue and document change feed triggers.
"""

from __future__ import annotations

from typing import Final

from alembic import op

# Revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


MODEL_TABLE_SQL: Final[tuple[str, ...]] = (
    """
    CREATE TABLE api_keys (
    	user_id UUID NOT NULL, 
    	name VARCHAR(100), 
    	prefix VARCHAR(32) NOT NULL, 
    	hashed_secret VARCHAR(128) NOT NULL, 
    	expires_at TIMESTAMP WITH TIME ZONE, 
    	revoked_at TIMESTAMP WITH TIME ZONE, 
    	last_used_at TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_api_keys PRIMARY KEY (id), 
    	CONSTRAINT uq_api_keys_prefix UNIQUE (prefix), 
    	CONSTRAINT uq_api_keys_hashed_secret UNIQUE (hashed_secret)
    );
    """,
    """
    CREATE TABLE application_settings (
    	id SMALLINT NOT NULL, 
    	schema_version INTEGER DEFAULT 2 NOT NULL, 
    	data JSONB DEFAULT '{}'::jsonb NOT NULL, 
    	revision BIGINT DEFAULT 1 NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    	updated_by UUID, 
    	CONSTRAINT pk_application_settings PRIMARY KEY (id), 
    	CONSTRAINT ck_application_settings_ck_application_settings_singleton CHECK (id = 1), 
    	CONSTRAINT ck_application_settings_ck_application_settings_data_object CHECK (jsonb_typeof(data) = 'object')
    );
    """,
    """
    CREATE TABLE auth_sessions (
    	user_id UUID NOT NULL, 
    	token_hash VARCHAR(128) NOT NULL, 
    	auth_method VARCHAR(32) DEFAULT 'unknown' NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    	expires_at TIMESTAMP WITH TIME ZONE, 
    	revoked_at TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_auth_sessions PRIMARY KEY (id), 
    	CONSTRAINT ck_auth_sessions_ck_auth_sessions_auth_method CHECK (auth_method IN ('password', 'sso', 'unknown')), 
    	CONSTRAINT uq_auth_sessions_token_hash UNIQUE (token_hash)
    );
    """,
    """
    CREATE TABLE configurations (
    	workspace_id UUID NOT NULL, 
    	display_name VARCHAR(255) NOT NULL, 
    	status VARCHAR(20) DEFAULT 'draft' NOT NULL, 
    	source_configuration_id UUID, 
    	source_kind VARCHAR(20) DEFAULT 'template' NOT NULL, 
    	notes TEXT, 
    	published_digest VARCHAR(80), 
    	last_used_at TIMESTAMP WITH TIME ZONE, 
    	activated_at TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_configurations PRIMARY KEY (id)
    );
    """,
    """
    CREATE TABLE document_views (
    	workspace_id UUID NOT NULL, 
    	name VARCHAR(120) NOT NULL, 
    	name_key VARCHAR(120) NOT NULL, 
    	visibility VARCHAR(20) NOT NULL, 
    	owner_user_id UUID, 
    	query_state JSONB NOT NULL, 
    	table_state JSONB NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_document_views PRIMARY KEY (id), 
    	CONSTRAINT ck_document_views_document_views_visibility_owner CHECK ((visibility = 'private' AND owner_user_id IS NOT NULL) OR (visibility = 'public' AND owner_user_id IS NULL))
    );
    """,
    """
    CREATE TABLE file_comment_mentions (
    	comment_id UUID NOT NULL, 
    	mentioned_user_id UUID NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_file_comment_mentions PRIMARY KEY (id), 
    	CONSTRAINT file_comment_mentions_comment_user_key UNIQUE (comment_id, mentioned_user_id)
    );
    """,
    """
    CREATE TABLE file_comments (
    	workspace_id UUID NOT NULL, 
    	file_id UUID NOT NULL, 
    	author_user_id UUID NOT NULL, 
    	body TEXT NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_file_comments PRIMARY KEY (id)
    );
    """,
    """
    CREATE TABLE file_tags (
    	file_id UUID NOT NULL, 
    	tag VARCHAR(100) NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_file_tags PRIMARY KEY (id), 
    	CONSTRAINT file_tags_file_id_tag_key UNIQUE (file_id, tag)
    );
    """,
    """
    CREATE TABLE file_versions (
    	file_id UUID NOT NULL, 
    	version_no INTEGER NOT NULL, 
    	origin VARCHAR(50) DEFAULT 'uploaded' NOT NULL, 
    	run_id UUID, 
    	created_by_user_id UUID, 
    	sha256 VARCHAR(64) NOT NULL, 
    	byte_size INTEGER NOT NULL, 
    	content_type VARCHAR(255), 
    	filename_at_upload VARCHAR(255) NOT NULL, 
    	storage_version_id VARCHAR(128), 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_file_versions PRIMARY KEY (id), 
    	CONSTRAINT file_versions_file_id_version_no_key UNIQUE (file_id, version_no)
    );
    """,
    """
    CREATE TABLE files (
    	workspace_id UUID NOT NULL, 
    	kind VARCHAR(50) DEFAULT 'input' NOT NULL, 
    	name VARCHAR(255) NOT NULL, 
    	name_key VARCHAR(255) NOT NULL, 
    	blob_name VARCHAR(512) NOT NULL, 
    	current_version_id UUID, 
    	source_file_id UUID, 
    	comment_count INTEGER DEFAULT '0' NOT NULL, 
    	attributes JSONB NOT NULL, 
    	uploaded_by_user_id UUID, 
    	assignee_user_id UUID, 
    	last_run_id UUID, 
    	deleted_at TIMESTAMP WITH TIME ZONE, 
    	deleted_by_user_id UUID, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_files PRIMARY KEY (id)
    );
    """,
    """
    CREATE TABLE mfa_challenges (
    	user_id UUID NOT NULL, 
    	challenge_hash VARCHAR(128) NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	consumed_at TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_mfa_challenges PRIMARY KEY (id), 
    	CONSTRAINT uq_mfa_challenges_challenge_hash UNIQUE (challenge_hash)
    );
    """,
    """
    CREATE TABLE oauth_accounts (
    	user_id UUID NOT NULL, 
    	oauth_name VARCHAR(100) NOT NULL, 
    	account_id VARCHAR(255) NOT NULL, 
    	account_email VARCHAR(320), 
    	access_token TEXT NOT NULL, 
    	refresh_token TEXT, 
    	expires_at TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_oauth_accounts PRIMARY KEY (id), 
    	CONSTRAINT uq_oauth_accounts_name_account UNIQUE (oauth_name, account_id)
    );
    """,
    """
    CREATE TABLE password_reset_tokens (
    	user_id UUID NOT NULL, 
    	token_hash VARCHAR(128) NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	consumed_at TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_password_reset_tokens PRIMARY KEY (id), 
    	CONSTRAINT uq_password_reset_tokens_token_hash UNIQUE (token_hash)
    );
    """,
    """
    CREATE TABLE permissions (
    	key VARCHAR(120) NOT NULL, 
    	resource VARCHAR(120) NOT NULL, 
    	action VARCHAR(120) NOT NULL, 
    	scope_type VARCHAR(20) NOT NULL, 
    	label VARCHAR(200) NOT NULL, 
    	description TEXT NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_permissions PRIMARY KEY (id), 
    	CONSTRAINT uq_permissions_key UNIQUE (key)
    );
    """,
    """
    CREATE TABLE role_permissions (
    	role_id UUID NOT NULL, 
    	permission_id UUID NOT NULL, 
    	CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id)
    );
    """,
    """
    CREATE TABLE roles (
    	slug VARCHAR(100) NOT NULL, 
    	name VARCHAR(150) NOT NULL, 
    	description TEXT, 
    	is_system BOOLEAN DEFAULT false NOT NULL, 
    	is_editable BOOLEAN DEFAULT true NOT NULL, 
    	created_by_id UUID, 
    	updated_by_id UUID, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_roles PRIMARY KEY (id), 
    	CONSTRAINT uq_roles_slug UNIQUE (slug)
    );
    """,
    """
    CREATE TABLE run_fields (
    	run_id UUID NOT NULL, 
    	field VARCHAR(128) NOT NULL, 
    	label VARCHAR(255), 
    	detected BOOLEAN NOT NULL, 
    	best_mapping_score FLOAT, 
    	occurrences_tables INTEGER NOT NULL, 
    	occurrences_columns INTEGER NOT NULL, 
    	CONSTRAINT pk_run_fields PRIMARY KEY (run_id, field)
    );
    """,
    """
    CREATE TABLE run_metrics (
    	run_id UUID NOT NULL, 
    	evaluation_outcome VARCHAR(20), 
    	evaluation_findings_total INTEGER, 
    	evaluation_findings_info INTEGER, 
    	evaluation_findings_warning INTEGER, 
    	evaluation_findings_error INTEGER, 
    	validation_issues_total INTEGER, 
    	validation_issues_info INTEGER, 
    	validation_issues_warning INTEGER, 
    	validation_issues_error INTEGER, 
    	validation_max_severity VARCHAR(10), 
    	workbook_count INTEGER, 
    	sheet_count INTEGER, 
    	table_count INTEGER, 
    	row_count_total INTEGER, 
    	row_count_empty INTEGER, 
    	column_count_total INTEGER, 
    	column_count_empty INTEGER, 
    	column_count_mapped INTEGER, 
    	column_count_unmapped INTEGER, 
    	field_count_expected INTEGER, 
    	field_count_detected INTEGER, 
    	field_count_not_detected INTEGER, 
    	cell_count_total INTEGER, 
    	cell_count_non_empty INTEGER, 
    	CONSTRAINT pk_run_metrics PRIMARY KEY (run_id)
    );
    """,
    """
    CREATE TABLE run_table_columns (
    	run_id UUID NOT NULL, 
    	workbook_index INTEGER NOT NULL, 
    	workbook_name VARCHAR(255) NOT NULL, 
    	sheet_index INTEGER NOT NULL, 
    	sheet_name VARCHAR(255) NOT NULL, 
    	table_index INTEGER NOT NULL, 
    	column_index INTEGER NOT NULL, 
    	header_raw TEXT, 
    	header_normalized TEXT, 
    	non_empty_cells INTEGER NOT NULL, 
    	mapping_status VARCHAR(32) NOT NULL, 
    	mapped_field VARCHAR(128), 
    	mapping_score FLOAT, 
    	mapping_method VARCHAR(32), 
    	unmapped_reason VARCHAR(64), 
    	CONSTRAINT pk_run_table_columns PRIMARY KEY (run_id, workbook_index, sheet_index, table_index, column_index)
    );
    """,
    """
    CREATE TABLE runs (
    	configuration_id UUID NOT NULL, 
    	workspace_id UUID NOT NULL, 
    	input_file_version_id UUID, 
    	run_options JSONB, 
    	input_sheet_names JSONB, 
    	output_file_version_id UUID, 
    	deps_digest VARCHAR(128) NOT NULL, 
    	available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	attempt_count INTEGER NOT NULL, 
    	max_attempts INTEGER NOT NULL, 
    	claimed_by VARCHAR(255), 
    	claim_expires_at TIMESTAMP WITH TIME ZONE, 
    	operation VARCHAR(20) DEFAULT 'process' NOT NULL, 
    	status VARCHAR(20) DEFAULT 'queued' NOT NULL, 
    	exit_code INTEGER, 
    	submitted_by_user_id UUID, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	started_at TIMESTAMP WITH TIME ZONE, 
    	completed_at TIMESTAMP WITH TIME ZONE, 
    	error_message TEXT, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_runs PRIMARY KEY (id)
    );
    """,
    """
    CREATE TABLE sso_auth_states (
    	state VARCHAR(255) NOT NULL, 
    	provider_id VARCHAR(64) NOT NULL, 
    	nonce VARCHAR(255) NOT NULL, 
    	pkce_verifier VARCHAR(255) NOT NULL, 
    	return_to VARCHAR(2048) NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	consumed_at TIMESTAMP WITH TIME ZONE, 
    	CONSTRAINT pk_sso_auth_states PRIMARY KEY (state)
    );
    """,
    """
    CREATE TABLE sso_identities (
    	provider_id VARCHAR(64) NOT NULL, 
    	subject VARCHAR(255) NOT NULL, 
    	user_id UUID NOT NULL, 
    	email VARCHAR(320), 
    	email_verified BOOLEAN, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	CONSTRAINT pk_sso_identities PRIMARY KEY (id), 
    	CONSTRAINT uq_sso_identities_provider_subject UNIQUE (provider_id, subject), 
    	CONSTRAINT uq_sso_identities_provider_user UNIQUE (provider_id, user_id)
    );
    """,
    """
    CREATE TABLE sso_provider_domains (
    	provider_id VARCHAR(64) NOT NULL, 
    	domain VARCHAR(255) NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_sso_provider_domains PRIMARY KEY (provider_id, domain), 
    	CONSTRAINT uq_sso_provider_domains_domain UNIQUE (domain)
    );
    """,
    """
    CREATE TABLE sso_providers (
    	id VARCHAR(64) NOT NULL, 
    	type VARCHAR(20) DEFAULT 'oidc' NOT NULL, 
    	label VARCHAR(255) NOT NULL, 
    	issuer VARCHAR(512) NOT NULL, 
    	client_id VARCHAR(255) NOT NULL, 
    	client_secret_enc TEXT NOT NULL, 
    	status VARCHAR(20) DEFAULT 'disabled' NOT NULL, 
    	managed_by VARCHAR(20) DEFAULT 'db' NOT NULL, 
    	locked BOOLEAN DEFAULT false NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_sso_providers PRIMARY KEY (id)
    );
    """,
    """
    CREATE TABLE system_settings (
    	key VARCHAR(100) NOT NULL, 
    	value JSONB NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_system_settings PRIMARY KEY (key)
    );
    """,
    """
    CREATE TABLE user_mfa_totp (
    	user_id UUID NOT NULL, 
    	secret_enc TEXT NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    	enrolled_at TIMESTAMP WITH TIME ZONE, 
    	verified_at TIMESTAMP WITH TIME ZONE, 
    	recovery_code_hashes JSONB DEFAULT '[]' NOT NULL, 
    	CONSTRAINT pk_user_mfa_totp PRIMARY KEY (user_id)
    );
    """,
    """
    CREATE TABLE user_role_assignments (
    	user_id UUID NOT NULL, 
    	role_id UUID NOT NULL, 
    	workspace_id UUID, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_user_role_assignments PRIMARY KEY (id), 
    	CONSTRAINT uq_user_role_assignment_scope UNIQUE (user_id, role_id, workspace_id)
    );
    """,
    """
    CREATE TABLE users (
    	email VARCHAR(320) NOT NULL, 
    	email_normalized VARCHAR(320) NOT NULL, 
    	hashed_password VARCHAR(255) NOT NULL, 
    	display_name VARCHAR(255), 
    	is_service_account BOOLEAN NOT NULL, 
    	is_active BOOLEAN NOT NULL, 
    	is_verified BOOLEAN NOT NULL, 
    	must_change_password BOOLEAN DEFAULT false NOT NULL, 
    	last_login_at TIMESTAMP WITH TIME ZONE, 
    	failed_login_count INTEGER NOT NULL, 
    	locked_until TIMESTAMP WITH TIME ZONE, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_users PRIMARY KEY (id), 
    	CONSTRAINT uq_users_email_normalized UNIQUE (email_normalized)
    );
    """,
    """
    CREATE TABLE workspace_memberships (
    	user_id UUID NOT NULL, 
    	workspace_id UUID NOT NULL, 
    	is_default BOOLEAN NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_workspace_memberships PRIMARY KEY (user_id, workspace_id)
    );
    """,
    """
    CREATE TABLE workspaces (
    	name VARCHAR(255) NOT NULL, 
    	slug VARCHAR(100) NOT NULL, 
    	settings JSONB NOT NULL, 
    	id UUID DEFAULT uuidv7() NOT NULL, 
    	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    	CONSTRAINT pk_workspaces PRIMARY KEY (id), 
    	CONSTRAINT uq_workspaces_slug UNIQUE (slug)
    );
    """,
)


MODEL_FOREIGN_KEY_SQL: Final[tuple[str, ...]] = (
    """
    ALTER TABLE api_keys ADD CONSTRAINT fk_api_keys_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE auth_sessions ADD CONSTRAINT fk_auth_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE configurations ADD CONSTRAINT fk_configurations_source_configuration_id_configurations FOREIGN KEY(source_configuration_id) REFERENCES configurations (id) ON DELETE SET NULL;
    """,
    """
    ALTER TABLE configurations ADD CONSTRAINT fk_configurations_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE document_views ADD CONSTRAINT fk_document_views_owner_user_id_users FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE document_views ADD CONSTRAINT fk_document_views_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_comment_mentions ADD CONSTRAINT fk_file_comment_mentions_comment_id_file_comments FOREIGN KEY(comment_id) REFERENCES file_comments (id) ON DELETE CASCADE;
    """,
    """
    ALTER TABLE file_comment_mentions ADD CONSTRAINT fk_file_comment_mentions_mentioned_user_id_users FOREIGN KEY(mentioned_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_comments ADD CONSTRAINT fk_file_comments_author_user_id_users FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_comments ADD CONSTRAINT fk_file_comments_file_id_files FOREIGN KEY(file_id) REFERENCES files (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_comments ADD CONSTRAINT fk_file_comments_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_tags ADD CONSTRAINT fk_file_tags_file_id_files FOREIGN KEY(file_id) REFERENCES files (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_versions ADD CONSTRAINT fk_file_versions_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_versions ADD CONSTRAINT fk_file_versions_file_id_files FOREIGN KEY(file_id) REFERENCES files (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE file_versions ADD CONSTRAINT fk_file_versions_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE files ADD CONSTRAINT fk_files_assignee_user_id_users FOREIGN KEY(assignee_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE files ADD CONSTRAINT fk_files_current_version_id_file_versions FOREIGN KEY(current_version_id) REFERENCES file_versions (id) ON DELETE SET NULL;
    """,
    """
    ALTER TABLE files ADD CONSTRAINT fk_files_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE files ADD CONSTRAINT fk_files_source_file_id_files FOREIGN KEY(source_file_id) REFERENCES files (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE files ADD CONSTRAINT fk_files_uploaded_by_user_id_users FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE files ADD CONSTRAINT fk_files_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE mfa_challenges ADD CONSTRAINT fk_mfa_challenges_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE oauth_accounts ADD CONSTRAINT fk_oauth_accounts_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE password_reset_tokens ADD CONSTRAINT fk_password_reset_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE role_permissions ADD CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE role_permissions ADD CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE roles ADD CONSTRAINT fk_roles_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE roles ADD CONSTRAINT fk_roles_updated_by_id_users FOREIGN KEY(updated_by_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE run_fields ADD CONSTRAINT fk_run_fields_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE run_metrics ADD CONSTRAINT fk_run_metrics_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE run_table_columns ADD CONSTRAINT fk_run_table_columns_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE runs ADD CONSTRAINT fk_runs_configuration_id_configurations FOREIGN KEY(configuration_id) REFERENCES configurations (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE runs ADD CONSTRAINT fk_runs_input_file_version_id_file_versions FOREIGN KEY(input_file_version_id) REFERENCES file_versions (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE runs ADD CONSTRAINT fk_runs_output_file_version_id_file_versions FOREIGN KEY(output_file_version_id) REFERENCES file_versions (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE runs ADD CONSTRAINT fk_runs_submitted_by_user_id_users FOREIGN KEY(submitted_by_user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE runs ADD CONSTRAINT fk_runs_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE sso_auth_states ADD CONSTRAINT fk_sso_auth_states_provider_id_sso_providers FOREIGN KEY(provider_id) REFERENCES sso_providers (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE sso_identities ADD CONSTRAINT fk_sso_identities_provider_id_sso_providers FOREIGN KEY(provider_id) REFERENCES sso_providers (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE sso_identities ADD CONSTRAINT fk_sso_identities_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE sso_provider_domains ADD CONSTRAINT fk_sso_provider_domains_provider_id_sso_providers FOREIGN KEY(provider_id) REFERENCES sso_providers (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE user_mfa_totp ADD CONSTRAINT fk_user_mfa_totp_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE user_role_assignments ADD CONSTRAINT fk_user_role_assignments_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE user_role_assignments ADD CONSTRAINT fk_user_role_assignments_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE user_role_assignments ADD CONSTRAINT fk_user_role_assignments_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE workspace_memberships ADD CONSTRAINT fk_workspace_memberships_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE NO ACTION;
    """,
    """
    ALTER TABLE workspace_memberships ADD CONSTRAINT fk_workspace_memberships_workspace_id_workspaces FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE NO ACTION;
    """,
)


MODEL_INDEX_SQL: Final[tuple[str, ...]] = (
    """
    CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);
    """,
    """
    CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at);
    """,
    """
    CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);
    """,
    """
    CREATE INDEX ix_configurations_workspace_source ON configurations (workspace_id, source_configuration_id);
    """,
    """
    CREATE INDEX ix_configurations_workspace_status ON configurations (workspace_id, status);
    """,
    """
    CREATE INDEX ix_document_views_workspace_owner ON document_views (workspace_id, owner_user_id);
    """,
    """
    CREATE INDEX ix_document_views_workspace_visibility ON document_views (workspace_id, visibility);
    """,
    """
    CREATE UNIQUE INDEX uq_document_views_workspace_private_owner_name_key ON document_views (workspace_id, owner_user_id, name_key) WHERE visibility = 'private';
    """,
    """
    CREATE UNIQUE INDEX uq_document_views_workspace_public_name_key ON document_views (workspace_id, name_key) WHERE visibility = 'public';
    """,
    """
    CREATE INDEX ix_file_comment_mentions_comment ON file_comment_mentions (comment_id);
    """,
    """
    CREATE INDEX ix_file_comment_mentions_user ON file_comment_mentions (mentioned_user_id);
    """,
    """
    CREATE INDEX ix_file_comments_file_created ON file_comments (file_id, created_at);
    """,
    """
    CREATE INDEX ix_file_comments_workspace_created ON file_comments (workspace_id, created_at);
    """,
    """
    CREATE INDEX file_tags_tag_file_id_idx ON file_tags (tag, file_id);
    """,
    """
    CREATE INDEX ix_file_tags_file_id ON file_tags (file_id);
    """,
    """
    CREATE INDEX ix_file_tags_tag ON file_tags (tag);
    """,
    """
    CREATE INDEX ix_file_versions_file_id_created ON file_versions (file_id, created_at);
    """,
    """
    CREATE INDEX ix_file_versions_file_id_version ON file_versions (file_id, version_no);
    """,
    """
    CREATE UNIQUE INDEX files_workspace_kind_name_key ON files (workspace_id, kind, name_key) WHERE deleted_at IS NULL;
    """,
    """
    CREATE INDEX ix_files_workspace_assignee ON files (workspace_id, assignee_user_id);
    """,
    """
    CREATE INDEX ix_files_workspace_created ON files (workspace_id, created_at);
    """,
    """
    CREATE INDEX ix_files_workspace_last_run_id ON files (workspace_id, last_run_id);
    """,
    """
    CREATE INDEX ix_files_workspace_uploader ON files (workspace_id, uploaded_by_user_id);
    """,
    """
    CREATE INDEX ix_mfa_challenges_expires_at ON mfa_challenges (expires_at);
    """,
    """
    CREATE INDEX ix_mfa_challenges_user_id ON mfa_challenges (user_id);
    """,
    """
    CREATE INDEX ix_password_reset_tokens_expires_at ON password_reset_tokens (expires_at);
    """,
    """
    CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);
    """,
    """
    CREATE INDEX ix_roles_slug ON roles (slug);
    """,
    """
    CREATE INDEX ix_runs_claim ON runs (status, available_at, created_at);
    """,
    """
    CREATE INDEX ix_runs_claim_expires ON runs (status, claim_expires_at);
    """,
    """
    CREATE INDEX ix_runs_configuration ON runs (configuration_id);
    """,
    """
    CREATE INDEX ix_runs_input_file_version ON runs (input_file_version_id);
    """,
    """
    CREATE INDEX ix_runs_operation ON runs (operation);
    """,
    """
    CREATE INDEX ix_runs_status ON runs (status);
    """,
    """
    CREATE INDEX ix_runs_status_completed ON runs (status, completed_at);
    """,
    """
    CREATE INDEX ix_runs_status_created_at ON runs (status, created_at);
    """,
    """
    CREATE INDEX ix_runs_workspace ON runs (workspace_id);
    """,
    """
    CREATE INDEX ix_runs_workspace_created ON runs (workspace_id, created_at);
    """,
    """
    CREATE INDEX ix_runs_workspace_input_finished ON runs (workspace_id, input_file_version_id, completed_at, started_at);
    """,
    """
    CREATE UNIQUE INDEX uq_runs_active_job ON runs (workspace_id, input_file_version_id, configuration_id) WHERE status IN ('queued','running') AND operation = 'process';
    """,
    """
    CREATE UNIQUE INDEX uq_runs_active_publish ON runs (configuration_id) WHERE status IN ('queued','running') AND operation = 'publish';
    """,
    """
    CREATE INDEX ix_sso_auth_states_expires ON sso_auth_states (expires_at);
    """,
    """
    CREATE INDEX ix_sso_auth_states_provider ON sso_auth_states (provider_id);
    """,
    """
    CREATE INDEX ix_sso_identities_provider_subject ON sso_identities (provider_id, subject);
    """,
    """
    CREATE INDEX ix_sso_identities_user ON sso_identities (user_id);
    """,
    """
    CREATE INDEX ix_sso_provider_domains_domain ON sso_provider_domains (domain);
    """,
    """
    CREATE INDEX ix_sso_provider_domains_provider ON sso_provider_domains (provider_id);
    """,
    """
    CREATE INDEX ix_sso_providers_issuer ON sso_providers (issuer);
    """,
    """
    CREATE INDEX ix_sso_providers_status ON sso_providers (status);
    """,
    """
    CREATE INDEX ix_user_role_assignments_user_id ON user_role_assignments (user_id);
    """,
    """
    CREATE INDEX ix_user_role_assignments_workspace_id ON user_role_assignments (workspace_id);
    """,
)


def _execute_statements(statements: tuple[str, ...]) -> None:
    for statement in statements:
        op.execute(statement)


def _create_uuidv7_function() -> None:
    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'uuidv7'
                  AND pg_function_is_visible(oid)
            ) THEN
                CREATE FUNCTION uuidv7() RETURNS uuid AS $func$
                DECLARE
                    ts_ms bigint;
                    ts_hex text;
                    rand_a int;
                    rand_a_hex text;
                    rand_b_hex text;
                    variant_nibble int;
                    uuid_hex text;
                BEGIN
                    ts_ms := floor(extract(epoch from clock_timestamp()) * 1000)::bigint;
                    ts_hex := lpad(to_hex(ts_ms), 12, '0');

                    rand_a := floor(random() * 4096)::int;
                    rand_a_hex := lpad(to_hex(rand_a), 3, '0');

                    rand_b_hex := lpad(to_hex(floor(random() * 4294967296)::bigint), 8, '0')
                               || lpad(to_hex(floor(random() * 4294967296)::bigint), 8, '0');
                    variant_nibble := (floor(random() * 4)::int) + 8;
                    rand_b_hex := to_hex(variant_nibble) || substring(rand_b_hex from 2);

                    uuid_hex := ts_hex || '7' || rand_a_hex || rand_b_hex;
                    RETURN (
                        substring(uuid_hex from 1 for 8) || '-' ||
                        substring(uuid_hex from 9 for 4) || '-' ||
                        substring(uuid_hex from 13 for 4) || '-' ||
                        substring(uuid_hex from 17 for 4) || '-' ||
                        substring(uuid_hex from 21 for 12)
                    )::uuid;
                END;
                $func$ LANGUAGE plpgsql;
            END IF;
        END
        $do$;
        """
    )


def _seed_application_settings() -> None:
    op.execute(
        """
        INSERT INTO application_settings (
            id,
            schema_version,
            data,
            revision,
            updated_at,
            updated_by
        )
        VALUES (1, 2, '{}'::jsonb, 1, now(), NULL)
        ON CONFLICT (id) DO NOTHING;
        """
    )


def _install_run_notify_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION fn_runs_notify_queued()
        RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'INSERT' AND NEW.status = 'queued')
               OR (TG_OP = 'UPDATE'
                   AND NEW.status = 'queued'
                   AND NEW.status IS DISTINCT FROM OLD.status) THEN
                PERFORM pg_notify('ade_run_queued', NEW.id::text);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_runs_notify_queued
        AFTER INSERT OR UPDATE OF status ON runs
        FOR EACH ROW
        EXECUTE FUNCTION fn_runs_notify_queued();
        """
    )


def _create_document_changes_objects() -> None:
    op.execute(
        """
        CREATE TABLE document_changes (
            id bigserial PRIMARY KEY,
            workspace_id uuid NOT NULL,
            document_id uuid NOT NULL,
            op text NOT NULL CHECK (op IN ('upsert', 'delete')),
            changed_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX ix_document_changes_workspace_id_id
            ON document_changes (workspace_id, id);
        CREATE INDEX ix_document_changes_document_id_id
            ON document_changes (document_id, id);
        CREATE INDEX ix_document_changes_changed_at
            ON document_changes (changed_at);
        """
    )

    op.execute(
        """
        CREATE FUNCTION record_document_change(
            _workspace_id uuid,
            _document_id uuid,
            _op text,
            _changed_at timestamptz
        )
        RETURNS bigint AS $$
        DECLARE
            _ts timestamptz;
            _id bigint;
        BEGIN
            IF _workspace_id IS NULL OR _document_id IS NULL OR _op IS NULL THEN
                RETURN NULL;
            END IF;
            _ts := COALESCE(_changed_at, clock_timestamp());
            INSERT INTO document_changes (workspace_id, document_id, op, changed_at)
            VALUES (_workspace_id, _document_id, _op, _ts)
            RETURNING id INTO _id;
            PERFORM pg_notify(
                'ade_document_changes',
                json_build_object(
                    'workspaceId', _workspace_id,
                    'documentId', _document_id,
                    'op', _op,
                    'id', _id
                )::text
            );
            RETURN _id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE FUNCTION trg_files_document_changes_insert()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.kind = 'input' THEN
                PERFORM record_document_change(
                    NEW.workspace_id,
                    NEW.id,
                    'upsert',
                    clock_timestamp()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE FUNCTION trg_files_document_changes_update()
        RETURNS trigger AS $$
        DECLARE
            _op text;
        BEGIN
            IF NEW.kind = 'input' AND (
                NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
                OR NEW.current_version_id IS DISTINCT FROM OLD.current_version_id
                OR NEW.name IS DISTINCT FROM OLD.name
                OR NEW.name_key IS DISTINCT FROM OLD.name_key
                OR NEW.attributes IS DISTINCT FROM OLD.attributes
                OR NEW.assignee_user_id IS DISTINCT FROM OLD.assignee_user_id
                OR NEW.comment_count IS DISTINCT FROM OLD.comment_count
                OR NEW.last_run_id IS DISTINCT FROM OLD.last_run_id
            ) THEN
                _op := CASE
                    WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN 'delete'
                    ELSE 'upsert'
                END;
                PERFORM record_document_change(
                    NEW.workspace_id,
                    NEW.id,
                    _op,
                    clock_timestamp()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE FUNCTION trg_file_tags_document_changes_insert()
        RETURNS trigger AS $$
        DECLARE
            _workspace_id uuid;
            _kind text;
        BEGIN
            SELECT workspace_id, kind
              INTO _workspace_id, _kind
              FROM files
             WHERE id = NEW.file_id;
            IF _workspace_id IS NOT NULL AND _kind = 'input' THEN
                PERFORM record_document_change(
                    _workspace_id,
                    NEW.file_id,
                    'upsert',
                    clock_timestamp()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE FUNCTION trg_file_tags_document_changes_delete()
        RETURNS trigger AS $$
        DECLARE
            _workspace_id uuid;
            _kind text;
        BEGIN
            SELECT workspace_id, kind
              INTO _workspace_id, _kind
              FROM files
             WHERE id = OLD.file_id;
            IF _workspace_id IS NOT NULL AND _kind = 'input' THEN
                PERFORM record_document_change(
                    _workspace_id,
                    OLD.file_id,
                    'upsert',
                    clock_timestamp()
                );
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE FUNCTION trg_runs_document_changes_insert()
        RETURNS trigger AS $$
        DECLARE
            _document_id uuid;
        BEGIN
            IF NEW.input_file_version_id IS NOT NULL THEN
                SELECT f.id
                  INTO _document_id
                  FROM file_versions AS fv
                  INNER JOIN files AS f ON f.id = fv.file_id
                 WHERE fv.id = NEW.input_file_version_id
                   AND f.kind = 'input';

                IF _document_id IS NOT NULL THEN
                    PERFORM record_document_change(
                        NEW.workspace_id,
                        _document_id,
                        'upsert',
                        clock_timestamp()
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE FUNCTION trg_runs_document_changes_update()
        RETURNS trigger AS $$
        DECLARE
            _document_id uuid;
        BEGIN
            IF NEW.input_file_version_id IS NOT NULL AND (
                NEW.status IS DISTINCT FROM OLD.status
                OR NEW.started_at IS DISTINCT FROM OLD.started_at
                OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
                OR NEW.output_file_version_id IS DISTINCT FROM OLD.output_file_version_id
                OR NEW.error_message IS DISTINCT FROM OLD.error_message
            ) THEN
                SELECT f.id
                  INTO _document_id
                  FROM file_versions AS fv
                  INNER JOIN files AS f ON f.id = fv.file_id
                 WHERE fv.id = NEW.input_file_version_id
                   AND f.kind = 'input';

                IF _document_id IS NOT NULL THEN
                    PERFORM record_document_change(
                        NEW.workspace_id,
                        _document_id,
                        'upsert',
                        clock_timestamp()
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def _install_document_change_triggers() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_files_document_changes_insert
        AFTER INSERT ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_document_changes_insert();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_files_document_changes_update
        AFTER UPDATE ON files
        FOR EACH ROW
        EXECUTE FUNCTION trg_files_document_changes_update();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_file_tags_document_changes_insert
        AFTER INSERT ON file_tags
        FOR EACH ROW
        EXECUTE FUNCTION trg_file_tags_document_changes_insert();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_file_tags_document_changes_delete
        AFTER DELETE ON file_tags
        FOR EACH ROW
        EXECUTE FUNCTION trg_file_tags_document_changes_delete();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_runs_document_changes_insert
        AFTER INSERT ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_document_changes_insert();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_runs_document_changes_update
        AFTER UPDATE ON runs
        FOR EACH ROW
        EXECUTE FUNCTION trg_runs_document_changes_update();
        """
    )


def upgrade() -> None:
    _create_uuidv7_function()
    _execute_statements(MODEL_TABLE_SQL)
    _execute_statements(MODEL_FOREIGN_KEY_SQL)
    _execute_statements(MODEL_INDEX_SQL)
    _seed_application_settings()
    _install_run_notify_trigger()
    _create_document_changes_objects()
    _install_document_change_triggers()


def downgrade() -> None:  # pragma: no cover
    raise NotImplementedError("Downgrades are not supported.")
